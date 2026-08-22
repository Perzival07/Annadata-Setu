import httpx
import base64
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from contracts.models import Diagnosis, PlotPassport
from contracts.client import get_plot_passport, get_nearby_outbreaks
from contracts.mock_data import PASSPORT as MOCK_PASSPORT
from brain.services.gemini import gemini_service

logger = logging.getLogger("brain.router.diagnose")

router = APIRouter(prefix="", tags=["Diagnosis"])

class DiagnoseRequest(BaseModel):
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    passport: Optional[PlotPassport] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

async def post_observation_telemetry(passport: PlotPassport, diagnosis: Diagnosis):
    """Quietly write the diagnosis to ground service as an epidemiological data point."""
    try:
        ground_url = "http://localhost:8003/observations"
        payload = {
            "geohash": passport.geohash,
            "plot_id": passport.plot_id,
            "lat": passport.lat,
            "lon": passport.lon,
            "district": passport.district,
            "crop": passport.inferred_crop,
            "disease": diagnosis.disease_name,
            "confidence": diagnosis.confidence,
            "is_action_needed": diagnosis.is_action_needed
        }
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(ground_url, json=payload)
            logger.info(f"Telemetry observation posted for plot {passport.plot_id}")
    except Exception as e:
        logger.warning(f"Telemetry write-back skipped (ground service offline/mock): {e}")

@router.post("/diagnose", response_model=Diagnosis)
async def diagnose(req: DiagnoseRequest, background_tasks: BackgroundTasks):
    """Primary diagnosis endpoint. Consumes image + plot context → returns Diagnosis."""
    # 1. Resolve PlotPassport
    passport = req.passport
    if not passport:
        if req.lat is not None and req.lon is not None:
            passport = await get_plot_passport(req.lat, req.lon)
        else:
            passport = MOCK_PASSPORT

    # 2. Decode image bytes if base64 provided
    image_bytes = None
    if req.image_base64:
        try:
            image_bytes = base64.b64decode(req.image_base64)
        except Exception as e:
            logger.warning(f"Failed to decode base64 image: {e}")
    elif req.image_url and not req.image_url.startswith("http://mock"):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(req.image_url)
                if res.status_code == 200:
                    image_bytes = res.content
        except Exception as e:
            logger.warning(f"Failed to fetch image_url {req.image_url}: {e}")

    # 3. Fetch nearby outbreaks context
    nearby = []
    try:
        outbreaks = await get_nearby_outbreaks(passport.lat, passport.lon)
        nearby = [o.model_dump() for o in outbreaks]
    except Exception as e:
        logger.warning(f"Failed to fetch nearby outbreaks: {e}")

    # 4. Diagnose with Gemini 2.5 Flash
    diagnosis = await gemini_service.diagnose_leaf(
        image_url=req.image_url,
        image_bytes=image_bytes,
        passport=passport,
        nearby_outbreaks=nearby
    )

    # 5. Queue background observation telemetry write
    background_tasks.add_task(post_observation_telemetry, passport, diagnosis)

    return diagnosis
