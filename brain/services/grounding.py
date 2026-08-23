"""The gather phase: Google Search grounding + function calling, before diagnosis.

WHY THIS IS A SEPARATE CALL
The Gemini API will not accept `tools` and a `response_schema` on the same
request — you get grounded free-form prose, or schema-locked JSON, not both.
BRAIN.md §7 makes the response schema non-negotiable ("a response schema on
every Gemini call — we take a structured field, never regex over prose"), so
tools cannot simply be bolted onto diagnose_leaf.

So the diagnosis runs in two phases:

  1. GATHER (here)  — tools on, no schema. The model searches the web and calls
                      our own services until it has what it needs, then writes
                      up its findings as notes.
  2. DECIDE (gemini.py) — tools off, Diagnosis schema on. The notes from phase 1
                      go in as context alongside the photo and the passport.

Phase 1 is entirely optional. Every failure path returns EMPTY, and a diagnosis
built without gathered context is exactly the diagnosis this service produced
before this module existed.

WHAT THE WEB MAY AND MAY NOT DO
Search grounding earns its place on questions the ICAR corpus structurally
cannot answer: whether a pathogen is being reported in this district this
season, whether a state advisory is live. It must never become a dosage source.
An ICAR Package of Practices is a reviewed document; a search result is a page
someone wrote. The gather prompt says so, and prompts/diagnosis.md repeats it on
the decide side, because only one of the two is enough to make it stick.

Citations are taken from the response's grounding_metadata — the URLs Google
says it actually retrieved — never from URLs the model writes in its prose.
That is the same discipline gemini.py already applies to ICAR filenames.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from brain.services.tools import (
    MAX_TOOL_ROUNDS,
    TOOL_SCHEMAS,
    execute_tool,
    gemini_tool_declarations,
)

logger = logging.getLogger("brain.grounding")

# Off by default: it adds a Gemini round-trip plus search latency to every
# diagnosis, and the demo runs on venue wifi (see brain/services/embeddings.py
# for the same reasoning). Set ENABLE_GEMINI_TOOLS=true to turn it on.
ENABLED = os.getenv("ENABLE_GEMINI_TOOLS", "false").lower() == "true"
# Whole-phase budget. Past this the farmer is better served by an ungrounded
# diagnosis now than a grounded one they have stopped waiting for.
GATHER_BUDGET_S = float(os.getenv("GEMINI_TOOLS_BUDGET_S", "20"))

GATHER_MODEL = "gemini-2.5-flash"

GATHER_INSTRUCTION = (
    "You are the research step of an Indian crop diagnosis pipeline. You are NOT "
    "writing the diagnosis — another model does that next, using your notes.\n\n"
    "Gather what that model will need:\n"
    "- Call retrieve_icar_docs to pull ICAR guidance on the symptoms you can see in "
    "the photo. Query it in the document's own vocabulary, and call it again with "
    "different wording if the first result does not match the image.\n"
    "- Call get_nearby_outbreaks to check whether your suspected disease is already "
    "spreading around this plot.\n"
    "- Use Google Search for what the documents cannot know: current disease "
    "reports, pest advisories or weather warnings for this district and season.\n\n"
    "HARD RULE: a chemical dosage may come ONLY from retrieve_icar_docs. Never take "
    "one from a web page, and never state one you have not seen in a retrieved "
    "document. If the documents give no dosage, write that down plainly.\n\n"
    "Then write your findings as short factual notes. Say which are from ICAR "
    "documents and which are from the web. State what you could NOT confirm — that "
    "is as useful as what you could."
)


class GatheredContext(BaseModel):
    """What phase 1 found. Empty is a valid, expected result."""

    notes: str = ""
    # [{"uri": ..., "title": ...}] straight from grounding_metadata.
    web_sources: List[Dict[str, str]] = []
    tools_called: List[str] = []
    search_used: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.notes.strip()

    def source_urls(self) -> List[str]:
        """Deduplicated URLs, in first-seen order, for Diagnosis.web_sources."""
        seen, urls = set(), []
        for s in self.web_sources:
            uri = (s.get("uri") or "").strip()
            if uri and uri not in seen:
                seen.add(uri)
                urls.append(uri)
        return urls


EMPTY = GatheredContext()


def _extract_web_sources(response) -> List[Dict[str, str]]:
    """Pull citations out of grounding_metadata.

    Deliberately does not read URLs out of the model's prose: a URL the model
    typed is a URL it may have invented, and this project has already shipped
    one uncheckable citation to farmers (see brain/tests/test_rag.py).
    """
    sources: List[Dict[str, str]] = []
    try:
        for candidate in response.candidates or []:
            metadata = getattr(candidate, "grounding_metadata", None)
            for chunk in getattr(metadata, "grounding_chunks", None) or []:
                web = getattr(chunk, "web", None)
                uri = getattr(web, "uri", None)
                if uri:
                    sources.append({"uri": uri, "title": getattr(web, "title", "") or uri})
    except Exception as e:
        logger.warning(f"Could not read grounding metadata: {e}")
    return sources


def _build_tool_configs(types):
    """Tool sets to try, most capable first.

    Not every model build accepts google_search alongside function declarations.
    Rather than guess from the model string, try the combination and step down
    on rejection — a wrong guess here silently costs either the search or the
    tools, and the log would not say which.
    """
    search = types.Tool(google_search=types.GoogleSearch())
    functions = gemini_tool_declarations()
    return [
        ("search+functions", [search, functions]),
        ("functions", [functions]),
        ("search", [search]),
    ]


async def _run_gather(client, types, contents: List[Any]) -> GatheredContext:
    """One gather conversation: call, service any function calls, repeat."""
    tool_ladder = _build_tool_configs(types)
    tools_called: List[str] = []
    web_sources: List[Dict[str, str]] = []
    search_used = False
    # Index into the ladder. Stepping down does not consume a tool round: a
    # rejected tool combination never reached the model, so it is not a turn.
    rung = 0
    rounds_used = 0

    while rounds_used < MAX_TOOL_ROUNDS:
        tool_label, tools = tool_ladder[rung]
        config = types.GenerateContentConfig(
            system_instruction=GATHER_INSTRUCTION,
            temperature=0.2,
            tools=tools,
        )

        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=GATHER_MODEL,
                contents=contents,
                config=config,
            )
        except Exception as e:
            # Step down the ladder only before the conversation has started:
            # mid-conversation the history already contains function calls, so
            # changing the tool set would invalidate it.
            if rounds_used == 0 and rung + 1 < len(tool_ladder):
                rung += 1
                logger.warning(
                    f"Gather rejected with tools={tool_label!r} ({e}); retrying with "
                    f"{tool_ladder[rung][0]!r}."
                )
                continue
            raise

        rounds_used += 1
        search_used = search_used or "search" in tool_label
        web_sources.extend(_extract_web_sources(response))

        calls = list(getattr(response, "function_calls", None) or [])
        if not calls:
            notes = (getattr(response, "text", None) or "").strip()
            return GatheredContext(
                notes=notes,
                web_sources=web_sources,
                tools_called=tools_called,
                search_used=search_used,
            )

        # Service every call the model asked for, concurrently — they are
        # independent reads and the model is blocked on all of them.
        results = await asyncio.gather(
            *(execute_tool(c.name, dict(c.args or {})) for c in calls)
        )
        tools_called.extend(c.name for c in calls)

        # function_calls came off a candidate, so there is one to echo back.
        contents.append(response.candidates[0].content)
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(name=call.name, response=result)
                    for call, result in zip(calls, results)
                ],
            )
        )

    logger.warning(
        f"Gather hit the {MAX_TOOL_ROUNDS}-round ceiling without settling; "
        f"using what it collected."
    )
    return GatheredContext(
        notes="",
        web_sources=web_sources,
        tools_called=tools_called,
        search_used=search_used,
    )


async def gather_context(
    client,
    passport,
    image_bytes: Optional[bytes] = None,
    nearby_outbreaks: Optional[List[Dict]] = None,
) -> GatheredContext:
    """Run phase 1. Returns EMPTY on any failure — never raises to the caller."""
    if not ENABLED or client is None:
        return EMPTY

    try:
        from google.genai import types

        brief = {
            "plot": passport.model_dump(mode="json"),
            "outbreaks_already_known": nearby_outbreaks or [],
        }
        parts: List[Any] = [
            types.Part.from_text(
                text=(
                    "Research this plot before it is diagnosed.\n"
                    f"{json.dumps(brief, indent=2, ensure_ascii=False, default=str)}"
                )
            )
        ]
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

        contents: List[Any] = [types.Content(role="user", parts=parts)]

        gathered = await asyncio.wait_for(
            _run_gather(client, types, contents), timeout=GATHER_BUDGET_S
        )
        logger.info(
            f"Gather finished: {len(gathered.notes)} chars of notes, "
            f"tools={gathered.tools_called}, web_sources={len(gathered.source_urls())}."
        )
        return gathered

    except asyncio.TimeoutError:
        logger.warning(
            f"Gather exceeded its {GATHER_BUDGET_S}s budget — diagnosing without it."
        )
        return EMPTY
    except Exception as e:
        logger.warning(f"Gather failed, diagnosing without it: {e}", exc_info=True)
        return EMPTY


def status() -> Dict[str, Any]:
    """Surfaced on /health so an operator can see whether tools are live."""
    return {
        "enabled": ENABLED,
        "model": GATHER_MODEL,
        "budget_seconds": GATHER_BUDGET_S,
        "max_tool_rounds": MAX_TOOL_ROUNDS,
        "declared_tools": [s["name"] for s in TOOL_SCHEMAS] + ["google_search"],
    }
