"""Gemini function-calling tools — the model pulls context instead of being fed it.

BRAIN.md §5-§7 describe a diagnosis that reasons over plot telemetry, the ICAR
corpus and nearby outbreaks. Until now all three were fetched unconditionally by
brain/routers/diagnose.py and pasted into the prompt, which means the model got
exactly one retrieval attempt with exactly one query string
("disease symptoms management stage N") no matter what the leaf actually showed.
A photo of purple-margined onion lesions and a photo of yellowing tomato tips
retrieved against the same sentence.

Declaring these as tools lets the model issue its OWN queries — "onion purple
blotch lesion white centre" — and re-query when the first pull is unhelpful.

Two rules hold for everything in this module:

1. A tool NEVER raises into the model loop. Every failure returns
   {"error": "..."} so the model can say it could not confirm something,
   rather than the whole diagnosis collapsing on a timeout.
2. Retrieved chunks keep their provenance. `retrieve_icar_docs` passes through
   the `source`/`provenance` tagging from rag.py unchanged, so a built-in note
   still cannot be cited to the farmer as a document (see brain/tests/test_rag.py).
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List

from brain.services.rag import rag_service

logger = logging.getLogger("brain.tools")

# A runaway tool loop is a runaway bill and a farmer staring at a spinner.
MAX_TOOL_ROUNDS = 4
# Per-call ceiling. The gather phase as a whole is already time-boxed by the
# caller; this stops one wedged dependency from eating the entire budget.
TOOL_TIMEOUT_S = 8.0


# --- Declarations -----------------------------------------------------------
# Kept as plain dicts rather than types.FunctionDeclaration objects so this
# module imports without the google-genai SDK present — brain/tests and the
# MOCK_MODE path both run in environments that do not have it installed.

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "retrieve_icar_docs",
        "description": (
            "Search the ingested ICAR Package of Practices corpus for agronomic "
            "guidance. Call this whenever you need to confirm a disease's "
            "symptoms, its management, or a dosage. Dosages may ONLY come from "
            "this tool. Call it more than once with different phrasings if the "
            "first result does not match what you see in the photo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "crop": {
                    "type": "string",
                    "description": "Crop name, e.g. 'Tomato', 'Onion'.",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "What you are looking for, in the words you would expect "
                        "the document to use — e.g. 'purple blotch lesion white "
                        "centre management'."
                    ),
                },
            },
            "required": ["crop", "query"],
        },
    },
    {
        "name": "get_nearby_outbreaks",
        "description": (
            "List confirmed disease clusters near a plot. Use this to check "
            "whether the disease you suspect is already spreading locally, which "
            "raises confidence, or whether it is absent, which lowers it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Plot latitude."},
                "lon": {"type": "number", "description": "Plot longitude."},
            },
            "required": ["lat", "lon"],
        },
    },
    {
        "name": "get_plot_passport",
        "description": (
            "Fetch satellite, soil and weather telemetry for a location. The "
            "plot under diagnosis is already in your context — use this only to "
            "compare against a NEIGHBOURING location, e.g. to check whether high "
            "humidity is local to this plot or regional."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude."},
                "lon": {"type": "number", "description": "Longitude."},
            },
            "required": ["lat", "lon"],
        },
    },
]


def gemini_tool_declarations():
    """TOOL_SCHEMAS as SDK objects. Raises if google-genai is absent — callers
    reach this only after confirming a live client."""
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(**schema) for schema in TOOL_SCHEMAS
        ]
    )


# --- Executors --------------------------------------------------------------

async def _retrieve_icar_docs(crop: str = "", query: str = "") -> Dict[str, Any]:
    # ChromaDB is synchronous; off-thread so a tool call cannot stall the loop.
    docs = await asyncio.to_thread(rag_service.retrieve_context, crop, query)
    return {
        "documents": [
            {
                "content": d["content"],
                # None here is load-bearing: it tells the model this text has no
                # citable document behind it.
                "source": d.get("source"),
                "provenance": d.get("provenance"),
            }
            for d in docs
        ],
        "citable": any(d.get("source") for d in docs),
    }


async def _get_nearby_outbreaks(lat: float = 0.0, lon: float = 0.0) -> Dict[str, Any]:
    from contracts.client import get_nearby_outbreaks

    outbreaks = await get_nearby_outbreaks(lat, lon)
    return {"outbreaks": [o.model_dump(mode="json") for o in outbreaks]}


async def _get_plot_passport(lat: float = 0.0, lon: float = 0.0) -> Dict[str, Any]:
    from contracts.client import get_plot_passport

    passport = await get_plot_passport(lat, lon)
    return {"passport": passport.model_dump(mode="json")}


EXECUTORS: Dict[str, Callable] = {
    "retrieve_icar_docs": _retrieve_icar_docs,
    "get_nearby_outbreaks": _get_nearby_outbreaks,
    "get_plot_passport": _get_plot_passport,
}


async def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run one model-requested tool call. Never raises."""
    executor = EXECUTORS.get(name)
    if not executor:
        logger.warning(f"Model requested unknown tool {name!r}.")
        return {"error": f"unknown tool {name!r}"}

    try:
        result = await asyncio.wait_for(executor(**(args or {})), timeout=TOOL_TIMEOUT_S)
        logger.info(f"Tool {name}({args}) succeeded.")
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Tool {name} timed out after {TOOL_TIMEOUT_S}s.")
        return {"error": f"{name} timed out; treat this information as unavailable"}
    except TypeError as e:
        # The model invented an argument. Tell it so, rather than dying.
        logger.warning(f"Tool {name} called with bad arguments {args}: {e}")
        return {"error": f"invalid arguments for {name}: {e}"}
    except Exception as e:
        logger.warning(f"Tool {name} failed: {e}")
        return {"error": f"{name} unavailable: {e}"}
