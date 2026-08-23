import os
import json
import asyncio
import logging
from typing import Dict, List, Optional

from contracts.models import Diagnosis, PlotPassport
from contracts.mock_data import DIAGNOSIS as MOCK_DIAGNOSIS
# Shared with channel/ — the same honest failure value must reach the farmer
# whether Gemini failed here or brain was unreachable from the pipeline.
from contracts.fallbacks import unavailable_diagnosis
from brain.services.rag import rag_service

logger = logging.getLogger("brain.gemini")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# BRAIN.md §6: escalate_to_human is True when confidence < 0.65.
CONFIDENCE_ESCALATION_THRESHOLD = 0.65



PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "diagnosis.md")

# BRAIN.md §5: the prompt is versioned in prompts/diagnosis.md — "edit here, not
# in code". It was not actually being read: the runtime instruction was a five
# line string inlined below, which silently dropped the file's ICAR compliance
# rule ("use dosages ONLY if backed by retrieved ICAR practices; never invent
# arbitrary chemical dosages") and its reasoning_context guidance. Editing the
# markdown changed nothing about what the model was told.
_FALLBACK_SYSTEM_INSTRUCTION = (
    "You are an expert Indian agronomist & plant pathologist. Examine the leaf photo and plot context.\n"
    "Return a strict JSON matching the Diagnosis schema.\n"
    "Cross-reference the visual symptoms against the plot's humidity, soil and growth stage — not the leaf alone.\n"
    "Use a dosage ONLY if it is backed by the retrieved ICAR documents. Never invent one; if the documents do not\n"
    "specify a dosage, say so in action_text and leave dosage null.\n"
    "If the leaf is healthy or shows abiotic nutrient deficiency (e.g. Nitrogen yellowing), set is_action_needed=False,\n"
    "dosage=null, and explain clearly in action_text how the farmer can save money by NOT spraying chemical fungicides.\n"
    "Populate reasoning_context[] with 2-4 facts you actually used.\n"
    "If confidence is < 0.65, set escalate_to_human=True."
)

_system_instruction_cache: Optional[str] = None


def load_system_instruction() -> str:
    """Read the versioned prompt, falling back to an equivalent inline copy.

    Only the prose above the `---` separator is sent: what follows it documents
    the JSON context this service injects programmatically, and feeding that
    template back to the model would just be noise.
    """
    global _system_instruction_cache
    if _system_instruction_cache is not None:
        return _system_instruction_cache

    try:
        with open(os.path.abspath(PROMPT_PATH), "r", encoding="utf-8") as f:
            text = f.read()
        instruction = text.split("\n---", 1)[0].strip()
        if not instruction:
            raise ValueError("prompt file has no system instruction section")
        logger.info(f"Loaded diagnosis system instruction from {PROMPT_PATH} ({len(instruction)} chars).")
    except Exception as e:
        # Never leave the model unprompted (BRAIN.md §9: fallbacks are mandatory).
        logger.warning(f"Could not read {PROMPT_PATH}, using inline fallback prompt: {e}")
        instruction = _FALLBACK_SYSTEM_INSTRUCTION

    _system_instruction_cache = instruction
    return instruction


class GeminiService:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if MOCK or not GEMINI_API_KEY:
            logger.info("GeminiService initialized in MOCK_MODE or missing API Key.")
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("Gemini 2.5 Client initialized successfully via google-genai SDK.")
        except Exception as e:
            logger.warning(f"Failed to initialize google-genai Client: {e}. Falling back to MOCK mode.")

    async def diagnose_leaf(
        self,
        image_url: Optional[str],
        image_bytes: Optional[bytes],
        passport: PlotPassport,
        nearby_outbreaks: Optional[List[Dict]] = None
    ) -> Diagnosis:
        """Call Gemini 2.5 Flash with strict Diagnosis Pydantic response schema."""
        # Deliberate mock mode is a development affordance (BRAIN.md §6) and
        # keeps returning the fixture. A missing client is a real failure and
        # must not be dressed up as one.
        if MOCK:
            logger.info("MOCK_MODE=true — returning the fixture Diagnosis.")
            return MOCK_DIAGNOSIS

        if not self.client:
            logger.error(
                "Gemini client unavailable (missing GEMINI_API_KEY or init failed) — "
                "escalating to human rather than guessing."
            )
            return unavailable_diagnosis()

        try:
            from google.genai import types

            # 1. Fetch relevant RAG chunks from ICAR database.
            # ChromaDB is synchronous; off-thread so it cannot stall the loop.
            rag_docs = await asyncio.to_thread(
                rag_service.retrieve_context,
                passport.inferred_crop,
                f"disease symptoms management stage {passport.crop_stage_days}",
            )
            # Only documents actually retrieved from the ingested corpus are
            # citable. Built-in notes carry source=None: labelling them with a
            # filename put a reference the farmer cannot check — and which does
            # not exist — at the bottom of the advisory.
            icar_sources = sorted({d["source"] for d in rag_docs if d.get("source")})
            has_corpus = bool(icar_sources)

            # 2. Build structured prompt context
            prompt_context = {
                "plot_passport": passport.model_dump(),
                "retrieved_icar_docs": [doc["content"] for doc in rag_docs],
                # Tell the model whether these came from a real document set. The
                # prompt forbids inventing a dosage; without this it cannot know
                # that the "retrieved" text is an unattributed built-in note.
                "retrieved_from_document_corpus": has_corpus,
                "nearby_outbreaks": nearby_outbreaks or []
            }

            system_instruction = load_system_instruction()

            user_content = [
                f"Diagnose this field plot context: {json.dumps(prompt_context, indent=2)}"
            ]

            # If image bytes exist, attach as image part
            if image_bytes:
                user_content.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=Diagnosis
            )

            # google-genai's generate_content is a blocking HTTP call. Awaiting
            # it directly would freeze the event loop for the full 3-8s of every
            # diagnosis, serialising all concurrent farmers behind one another.
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.5-flash",
                contents=user_content,
                config=config,
            )

            # Parse JSON output into Diagnosis Pydantic model
            raw_text = response.text
            if not raw_text:
                # A safety block or a truncated response yields no text. That is
                # "we do not know", not a reason to guess.
                raise ValueError("Gemini returned an empty response body")
            data = json.loads(raw_text)
            if not isinstance(data, dict):
                raise ValueError(f"Gemini returned {type(data).__name__}, expected a JSON object")

            # sources[] is the audit trail, so it must reflect what was really
            # retrieved rather than whatever the model chose to write there.
            data["sources"] = icar_sources

            diagnosis = Diagnosis(**data)

            # Confidence calibration (BRAIN.md §6): below 0.65 a human looks
            # at it. Enforced here rather than trusted to the model, which sets
            # the flag inconsistently.
            if diagnosis.confidence < CONFIDENCE_ESCALATION_THRESHOLD:
                diagnosis.escalate_to_human = True

            # An escalated diagnosis must carry no prescription. Leaving a dose
            # and a cost attached invites any renderer that forgets to check
            # escalate_to_human to bill the farmer for a spray we are unsure of.
            if diagnosis.escalate_to_human:
                diagnosis.dosage = None
                diagnosis.estimated_cost_inr = 0

            return diagnosis

        except Exception as e:
            # Covers API errors, timeouts, and a response that does not parse
            # into the Diagnosis schema. All of them mean "we do not know".
            logger.error(f"Gemini diagnosis failed, escalating to human: {e}", exc_info=True)
            return unavailable_diagnosis()

gemini_service = GeminiService()
