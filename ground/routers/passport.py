import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from contracts.models import PlotPassport
from ground.services.passport import passport_aggregator_service

logger = logging.getLogger("ground.router.passport")

router = APIRouter(prefix="", tags=["Plot Passport"])

class PassportRequest(BaseModel):
    lat: float = 19.9975
    lon: float = 73.7898
    # None, not "Nashik". These are overrides for callers that already know the
    # district — the officer dashboard does. Left unset, the pin is reverse
    # geocoded (ground/services/geocode.py); defaulting them to Nashik labelled
    # every farmer outside it with Nashik's district, telemetry fallbacks and
    # outbreak cluster.
    district: Optional[str] = None
    state: Optional[str] = None

@router.post("/plot-passport", response_model=PlotPassport)
async def generate_plot_passport(req: PassportRequest):
    """POST /plot-passport — Aggregate satellite, soil, weather & crop telemetry into PlotPassport."""
    passport = await passport_aggregator_service.build_plot_passport(
        lat=req.lat,
        lon=req.lon,
        district=req.district,
        state=req.state,
    )
    return passport
