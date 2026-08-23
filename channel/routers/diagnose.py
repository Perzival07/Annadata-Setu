import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from contracts.models import Diagnosis, PlotPassport
from contracts.client import get_plot_passport, diagnose_leaf
from contracts.fallbacks import unavailable_diagnosis
from channel.services.composer import composer_service
from channel.services.tts import tts_service
from channel.services.pipeline import _resolve_passport, _resolve_diagnosis as _pipeline_diagnosis

logger = logging.getLogger("channel.router.diagnose")

router = APIRouter(prefix="/api", tags=["PWA Diagnosis"])

class PWADiagnoseRequest(BaseModel):
    image_url: Optional[str] = None
    # The browser holds the photo as a data: URI, which brain cannot fetch.
    # The PWA strips the prefix and sends the raw base64 here instead.
    image_base64: Optional[str] = None
    lat: float = 19.9975
    lon: float = 73.7898

class PWADiagnoseResponse(BaseModel):
    diagnosis: Diagnosis
    passport: PlotPassport
    formatted_text: str
    marathi_script: str

@router.post("/diagnose", response_model=PWADiagnoseResponse)
async def pwa_diagnose(req: PWADiagnoseRequest):
    """PWA fallback entry point: capture photo + geo location → return Diagnosis & Marathi script."""
    if not req.image_base64 and not req.image_url:
        raise HTTPException(status_code=400, detail="A leaf photo is required (image_base64 or image_url).")

    # 1. Plot context — an outage degrades context, it must not block the reply.
    passport = await _resolve_passport(req.lat, req.lon)

    # 2. Diagnosis — on failure this is an honest escalation, never the fixture.
    diagnosis = await _resolve_diagnosis(req.image_base64, req.image_url, passport)

    # 3. Compose text and voice script
    formatted_text = composer_service.compose_text_advisory(diagnosis)
    marathi_script = composer_service.compose_marathi_script(diagnosis)

    return PWADiagnoseResponse(
        diagnosis=diagnosis,
        passport=passport,
        formatted_text=formatted_text,
        marathi_script=marathi_script
    )


async def _resolve_diagnosis(image_b64, image_url, passport) -> Diagnosis:
    """Reuse the pipeline's failure policy so PWA and WhatsApp cannot diverge."""
    if image_b64:
        return await _pipeline_diagnosis(image_b64, passport)
    # A publicly reachable URL — brain fetches it itself.
    try:
        return await diagnose_leaf(image_url, passport)
    except Exception as e:
        logger.error(f"PWA diagnosis failed, escalating to human: {e}", exc_info=True)
        return unavailable_diagnosis()
