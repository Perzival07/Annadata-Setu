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
    district: Optional[str] = "Nashik"
    state: Optional[str] = "Maharashtra"

@router.post("/plot-passport", response_model=PlotPassport)
async def generate_plot_passport(req: PassportRequest):
    """POST /plot-passport — Aggregate satellite, soil, weather & crop telemetry into PlotPassport."""
    passport = await passport_aggregator_service.build_plot_passport(
        lat=req.lat,
        lon=req.lon,
        district=req.district or "Nashik",
        state=req.state or "Maharashtra"
    )
    return passport
