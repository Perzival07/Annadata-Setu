import os
import json
import logging
from typing import Dict, List, Optional

from contracts.models import Diagnosis, PlotPassport
from contracts.mock_data import DIAGNOSIS as MOCK_DIAGNOSIS
from brain.services.rag import rag_service

logger = logging.getLogger("brain.gemini")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
        if MOCK or not self.client:
            logger.info("Returning MOCK Diagnosis response.")
            return MOCK_DIAGNOSIS

        try:
            from google.genai import types

            # 1. Fetch relevant RAG chunks from ICAR database
            rag_docs = rag_service.retrieve_context(
                crop=passport.inferred_crop,
                query=f"disease symptoms management stage {passport.crop_stage_days}"
            )
            icar_sources = list(set([doc["source"] for doc in rag_docs]))

            # 2. Build structured prompt context
            prompt_context = {
                "plot_passport": passport.model_dump(),
                "retrieved_icar_docs": [doc["content"] for doc in rag_docs],
                "nearby_outbreaks": nearby_outbreaks or []
            }

            system_instruction = (
                "You are an expert Indian agronomist & plant pathologist. Examine the leaf photo and plot context.\n"
                "Return a strict JSON matching the Diagnosis schema.\n"
                "If the leaf is healthy or shows abiotic nutrient deficiency (e.g. Nitrogen yellowing), set is_action_needed=False, dosage=null, "
                "and explain clearly in action_text how the farmer can save money by NOT spraying chemical fungicides.\n"
                "If confidence is < 0.65, set escalate_to_human=True."
            )

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

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_content,
                config=config
            )

            # Parse JSON output into Diagnosis Pydantic model
            raw_text = response.text
            data = json.loads(raw_text)

            # Ensure ICAR sources are populated
            if "sources" not in data or not data["sources"]:
                data["sources"] = icar_sources

            diagnosis = Diagnosis(**data)

            # Confidence calibration
            if diagnosis.confidence < 0.65:
                diagnosis.escalate_to_human = True

            return diagnosis

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}. Falling back to MOCK_DIAGNOSIS.")
            return MOCK_DIAGNOSIS

gemini_service = GeminiService()
