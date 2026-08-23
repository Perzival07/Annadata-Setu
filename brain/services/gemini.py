import os
import re
import json
import asyncio
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

from contracts.models import Diagnosis, PlotPassport
from contracts.languages import DEFAULT_LANGUAGE, get, has_foreign_script
from contracts.mock_data import DIAGNOSIS as MOCK_DIAGNOSIS
# Shared with channel/ — the same honest failure value must reach the farmer
# whether Gemini failed here or brain was unreachable from the pipeline.
from contracts.fallbacks import unavailable_diagnosis
from brain.services.rag import rag_service
from brain.services.grounding import gather_context
from brain.services.genai_pool import gemini_pool

logger = logging.getLogger("brain.gemini")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
# Kept for callers and tests that check it. The pool is the real source of keys
# and also reads GEMINI_API_KEY_1, _2, ... — see brain/services/genai_pool.py.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configurable because a pinned model is a thing that expires. gemini-2.5-flash
# was hardcoded here and in grounding.py, and Google now refuses it for keys
# created after its retirement:
#   404 — "This model models/gemini-2.5-flash is no longer available to new
#          users. Please update your code to use models/gemini-3.6-flash"
# Every diagnosis on a new key 404'd, was caught by the except below, and came
# back as an escalation — the service looked like it was working and was
# quietly answering "we don't know" to everyone.
#
# Still pinned rather than an alias like gemini-flash-latest: this project pins
# what it is exercised against (see brain/requirements.txt). The env var is the
# escape hatch so the next retirement is a config change, not a code change.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# BRAIN.md §6: escalate_to_human is True when confidence < 0.65.
CONFIDENCE_ESCALATION_THRESHOLD = 0.65



PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
PROMPT_PATH = os.path.join(PROMPTS_DIR, "diagnosis.md")

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

_prompt_cache: Dict[str, str] = {}


class VoiceScript(BaseModel):
    """Schema-locked wrapper. BRAIN.md §7 requires a response schema on every
    Gemini call — we take a structured field, never regex over prose."""
    script: str


# Kept for callers importing the old name.
MarathiScript = VoiceScript


_FALLBACK_VOICE_INSTRUCTION = (
    "Convert the structured Diagnosis into a spoken advisory for a smallholder Indian farmer, in "
    "the target language named in the input context.\n"
    "Four short sentences: what the crop has, why (weather/stage), what to do, cost and urgency.\n"
    "Write ONLY in the target language, in its own script. Text in any other script is read aloud "
    "by that language's voice and comes out as noise. Translate disease names into the target "
    "language, drop Latin botanical binomials entirely, and write numbers in that language's "
    "digits (English keeps ASCII digits).\n"
    "If escalate_to_human is true, say the photo could not be assessed, tell them clearly NOT to "
    "spray, and that an expert will review it. Never state a dose in that case."
)


def load_prompt(filename: str, fallback: str) -> str:
    """Read a versioned prompt from brain/prompts/, falling back to an inline copy.

    Only the prose above the `---` separator is sent: what follows documents the
    JSON context this service injects programmatically.
    """
    if filename in _prompt_cache:
        return _prompt_cache[filename]

    path = os.path.abspath(os.path.join(PROMPTS_DIR, filename))
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        instruction = text.split("\n---", 1)[0].strip()
        if not instruction:
            raise ValueError("prompt file has no instruction section")
        logger.info(f"Loaded prompt {filename} ({len(instruction)} chars).")
    except Exception as e:
        # Never leave the model unprompted (BRAIN.md §9: fallbacks are mandatory).
        logger.warning(f"Could not read {path}, using inline fallback: {e}")
        instruction = fallback

    _prompt_cache[filename] = instruction
    return instruction


def load_system_instruction() -> str:
    return load_prompt("diagnosis.md", _FALLBACK_SYSTEM_INSTRUCTION)



class GeminiService:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if MOCK:
            logger.info("GeminiService initialized in MOCK_MODE.")
            return

        if not gemini_pool.is_available:
            logger.info("GeminiService has no usable API key.")
            return

        # `client` is now the pool: same role, but it fails over to another key
        # when one runs out of quota instead of turning every diagnosis into an
        # escalation for the rest of the day.
        self.client = gemini_pool
        logger.info(
            f"Gemini client ready via google-genai SDK "
            f"({gemini_pool.key_count} key(s), model {GEMINI_MODEL})."
        )

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

            # 2. Gather phase — the model researches with Google Search and our
            # own services before anything is decided (brain/services/grounding.py).
            # It cannot run on this call: the API refuses tools alongside the
            # response_schema below, and BRAIN.md §7 will not give up the schema.
            # Returns EMPTY when disabled or on any failure, and an empty gather
            # leaves the diagnosis exactly as it was before tools existed.
            gathered = await gather_context(
                self.client,
                passport,
                image_bytes=image_bytes,
                nearby_outbreaks=nearby_outbreaks,
            )

            # 3. Build structured prompt context
            prompt_context = {
                "plot_passport": passport.model_dump(),
                "retrieved_icar_docs": [doc["content"] for doc in rag_docs],
                # Tell the model whether these came from a real document set. The
                # prompt forbids inventing a dosage; without this it cannot know
                # that the "retrieved" text is an unattributed built-in note.
                "retrieved_from_document_corpus": has_corpus,
                "nearby_outbreaks": nearby_outbreaks or []
            }
            if not gathered.is_empty:
                # Labelled, not merged into retrieved_icar_docs. These notes are
                # partly web-derived, and the one thing a web page must never do
                # here is supply a dosage.
                prompt_context["research_notes"] = gathered.notes
                prompt_context["research_notes_caveat"] = (
                    "These notes come from a research step that used web search. "
                    "Treat them as context and corroboration only. A dosage may "
                    "come ONLY from retrieved_icar_docs, never from these notes."
                )

            system_instruction = load_system_instruction()

            user_content = [
                # default=str so an unexpected datetime from a caller degrades to
                # a readable string rather than raising into the escalation path.
                "Diagnose this field plot context: "
                + json.dumps(prompt_context, indent=2, default=str)
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

            # 4. Decide phase — tools off, schema on.
            # google-genai's generate_content is a blocking HTTP call. Awaiting
            # it directly would freeze the event loop for the full 3-8s of every
            # diagnosis, serialising all concurrent farmers behind one another.
            response = await self.client.generate(
                model=GEMINI_MODEL, contents=user_content, config=config
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

            # Both source lists are the audit trail, so they must reflect what
            # was really retrieved rather than whatever the model chose to write
            # there. web_sources comes from grounding_metadata — the URLs Google
            # reports having fetched — so a URL the model typed cannot get in.
            data["sources"] = icar_sources
            data["web_sources"] = gathered.source_urls()

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

    async def compose_voice_script(
        self,
        diagnosis: Diagnosis,
        passport: Optional[PlotPassport] = None,
        language: str = DEFAULT_LANGUAGE,
    ) -> Optional[str]:
        """Generate the spoken advisory directly in `language` (BRAIN.md §11, 15:30).

        Asking the model for the target language beats translating: the original
        approach interpolated English Diagnosis fields into Marathi sentence
        frames, so the mr-IN voice had to read an English sentence aloud.

        Returns None when generation is unavailable or the result is not usable,
        so the caller falls back to its own single-script template rather than
        speaking something wrong.
        """
        if MOCK or not self.client:
            return None

        lang = get(language)

        try:
            from google.genai import types

            system_instruction = load_prompt("reply_voice.md", _FALLBACK_VOICE_INSTRUCTION)
            context = {
                # First key, so the constraint the model most often breaks is
                # the first thing it reads.
                "target_language": {
                    "code": lang.code,
                    "name": lang.english_name,
                    "script": lang.script,
                },
                "diagnosis": diagnosis.model_dump(),
                "plot": {
                    "district": passport.district if passport else None,
                    "crop": passport.inferred_crop if passport else None,
                    "crop_stage_days": passport.crop_stage_days if passport else None,
                    "weather_10d": passport.weather_10d if passport else {},
                } if passport else {},
            }

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=VoiceScript,
            )
            response = await self.client.generate(
                model=GEMINI_MODEL,
                contents=[
                    f"Compose the spoken {lang.english_name} advisory for: "
                    f"{json.dumps(context, ensure_ascii=False)}"
                ],
                config=config,
            )
            raw = response.text
            if not raw:
                raise ValueError("empty response")
            script = (json.loads(raw) or {}).get("script", "").strip()

            if not script:
                raise ValueError("model returned no script")
            # The whole point is a script the target voice can speak. If another
            # script came back anyway, reject it rather than hand it to the voice
            # engine. What counts as foreign is relative to the target: Latin for
            # Marathi, Hindi and Bengali; Devanagari and Bengali for English.
            if has_foreign_script(script, lang.code):
                raise ValueError(
                    f"script contains text a {lang.bcp47} voice cannot read: {script[:80]!r}"
                )

            return script
        except Exception as e:
            logger.warning(f"Voice script generation failed, caller will use its template: {e}")
            return None

    async def compose_marathi_script(
        self,
        diagnosis: Diagnosis,
        passport: Optional[PlotPassport] = None,
    ) -> Optional[str]:
        """compose_voice_script pinned to Marathi. Kept for existing callers."""
        return await self.compose_voice_script(diagnosis, passport, DEFAULT_LANGUAGE)


gemini_service = GeminiService()
