import os
import httpx
import base64
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from contracts.models import Diagnosis, PlotPassport
from contracts.languages import DEFAULT_LANGUAGE, get
from contracts.client import get_plot_passport, get_nearby_outbreaks
from contracts.mock_data import PASSPORT as MOCK_PASSPORT
from contracts.fallbacks import unavailable_diagnosis
from brain.services.gemini import gemini_service

logger = logging.getLogger("brain.router.diagnose")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
GROUND_URL = os.getenv("GROUND_URL", "http://localhost:8003")

router = APIRouter(prefix="", tags=["Diagnosis"])

class DiagnoseRequest(BaseModel):
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    passport: Optional[PlotPassport] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

async def post_observation_telemetry(passport: PlotPassport, diagnosis: Diagnosis):
    """Quietly write the diagnosis to ground service as an epidemiological data point.

    This is the write half of "one farmer's question becomes everyone's early
    warning" (BRAIN.md §2). It was pinned to http://localhost:8003, which
    resolves to brain's own container on Cloud Run — every observation was
    silently dropped in production, so no cluster could ever form.
    """
    if MOCK:
        logger.info("MOCK_MODE=true — skipping observation telemetry write.")
        return

    # An escalated diagnosis names no disease. Recording "Undetermined" as an
    # epidemiological data point would pollute the clusters with non-findings.
    if diagnosis.escalate_to_human:
        logger.info(f"Skipping telemetry for escalated diagnosis on plot {passport.plot_id}.")
        return

    try:
        ground_url = f"{GROUND_URL}/observations"
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
            res = await client.post(ground_url, json=payload)
            res.raise_for_status()
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
        elif MOCK:
            passport = MOCK_PASSPORT
        else:
            # Silently substituting the Nashik tomato fixture would make Gemini
            # reason about someone else's plot and report it as this farmer's.
            raise HTTPException(
                status_code=400,
                detail="A passport, or lat/lon to build one from, is required.",
            )

    # 2. Decode image bytes if base64 provided
    image_bytes = None
    if req.image_base64:
        try:
            image_bytes = base64.b64decode(req.image_base64)
        except Exception as e:
            logger.warning(f"Failed to decode base64 image: {e}")
    elif req.image_url and not req.image_url.startswith("http://mock"):
        if req.image_url.startswith("data:"):
            # The caller should have stripped the prefix into image_base64.
            logger.warning("Received a data: URI in image_url — send image_base64 instead.")
        elif "graph.facebook.com" in req.image_url:
            # Meta media needs channel's bearer token; brain cannot fetch it.
            logger.warning("Received a Meta graph URL — channel must download the bytes and send image_base64.")
        else:
            try:
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                    res = await client.get(req.image_url)
                    if res.status_code == 200:
                        image_bytes = res.content
                    else:
                        logger.warning(f"image_url returned HTTP {res.status_code}")
            except Exception as e:
                logger.warning(f"Failed to fetch image_url {req.image_url}: {e}")

    if not image_bytes and not MOCK:
        # Without a photo there is nothing to diagnose. Answering from plot
        # context alone produces a confident disease name from no evidence.
        logger.error("No image bytes resolved — escalating to human.")
        return unavailable_diagnosis()

    # 3. Fetch nearby outbreaks context
    nearby = []
    try:
        outbreaks = await get_nearby_outbreaks(passport.lat, passport.lon)
        # mode="json" matters: Outbreak.first_seen is a datetime, and gemini.py
        # json.dumps() this straight into the prompt. In python mode that raised
        # TypeError inside the diagnosis try/except, so every plot that actually
        # had a nearby outbreak — the ones we most want the model to know about —
        # escalated to a human instead of being diagnosed.
        nearby = [o.model_dump(mode="json") for o in outbreaks]
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


class AdvisoryScriptRequest(BaseModel):
    diagnosis: Diagnosis
    passport: Optional[PlotPassport] = None
    # Defaults to Marathi so a caller that predates multi-language support gets
    # exactly what it got before.
    language: str = DEFAULT_LANGUAGE


class AdvisoryScriptResponse(BaseModel):
    script: Optional[str] = None
    language: str = DEFAULT_LANGUAGE
    generated_by: str  # "gemini" | "unavailable"


@router.post("/advisory-script", response_model=AdvisoryScriptResponse)
async def advisory_script(req: AdvisoryScriptRequest):
    """Spoken advisory in the farmer's language, generated rather than translated
    (BRAIN.md §11).

    Returns script=None when generation is unavailable, so the caller falls back
    to its own single-script template instead of speaking something wrong. The
    echoed `language` is the one actually used — an unsupported code resolves to
    the default rather than erroring, and the caller needs to know which it got.
    """
    lang = get(req.language)
    script = await gemini_service.compose_voice_script(
        req.diagnosis, req.passport, lang.code
    )
    return AdvisoryScriptResponse(
        script=script,
        language=lang.code,
        generated_by="gemini" if script else "unavailable",
    )
