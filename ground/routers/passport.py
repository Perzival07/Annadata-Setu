import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from contracts.models import PlotPassport
from ground.services.passport import passport_aggregator_service
from ground.services.geocode import geocode_service

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


class PlaceResponse(BaseModel):
    """Just where a coordinate is — no telemetry."""

    district: Optional[str] = None
    state: Optional[str] = None
    source: Optional[str] = None
    resolved: bool = False


@router.get("/place", response_model=PlaceResponse)
async def resolve_place(lat: float, lon: float):
    """GET /place — reverse geocode a pin, and nothing else.

    Exists for the web app's location capture, which wants to show the farmer
    which district they were placed in (and therefore which language they will
    be answered in) BEFORE they commit to a diagnosis. Going through
    /plot-passport for that would run Earth Engine, SoilGrids and the weather
    forecast to answer a question none of them are involved in.

    `resolved=false` means the pin could not be placed — offshore, or geocoding
    unavailable. The caller must not present a guess as an answer.
    """
    place = await geocode_service.reverse(lat, lon)
    if not place:
        return PlaceResponse(resolved=False)
    return PlaceResponse(
        district=place.district, state=place.state, source=place.source, resolved=True
    )
