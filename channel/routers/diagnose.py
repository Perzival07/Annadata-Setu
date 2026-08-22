import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from contracts.models import Diagnosis, PlotPassport
from contracts.client import get_plot_passport, diagnose_leaf
from channel.services.composer import composer_service
from channel.services.tts import tts_service

logger = logging.getLogger("channel.router.diagnose")

router = APIRouter(prefix="/api", tags=["PWA Diagnosis"])

class PWADiagnoseRequest(BaseModel):
    image_url: Optional[str] = None
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
    try:
        # 1. Fetch PlotPassport from Ground service
        passport = await get_plot_passport(req.lat, req.lon)

        # 2. Call Gemini Brain for Diagnosis
        diagnosis = await diagnose_leaf(req.image_url or "http://mock.url/leaf.jpg", passport)

        # 3. Compose text and voice script
        formatted_text = composer_service.compose_text_advisory(diagnosis)
        marathi_script = composer_service.compose_marathi_script(diagnosis)

        return PWADiagnoseResponse(
            diagnosis=diagnosis,
            passport=passport,
            formatted_text=formatted_text,
            marathi_script=marathi_script
        )
    except Exception as e:
        logger.error(f"PWA Diagnosis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
