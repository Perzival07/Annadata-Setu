import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from contracts.models import Outbreak
from contracts.mock_data import OUTBREAK as MOCK_OUTBREAK
from ground.services.firestore import firestore_service
from ground.services.geo import geo_service
from ground.services.cluster import clustering_service

logger = logging.getLogger("ground.router.observations")

router = APIRouter(prefix="", tags=["Observations Telemetry"])

class ObservationCreateRequest(BaseModel):
    geohash: str
    plot_id: str
    lat: float
    lon: float
    district: str
    crop: str
    disease: str
    confidence: float
    is_action_needed: bool

@router.post("/observations")
async def create_observation(req: ObservationCreateRequest):
    """POST /observations — Write a diagnosis telemetry data point."""
    obs_id = await firestore_service.save_observation(req.model_dump())
    return {"status": "created", "obs_id": obs_id}

@router.get("/outbreaks/nearby", response_model=List[Outbreak])
async def get_nearby_outbreaks(lat: float = 19.9975, lon: float = 73.7898):
    """GET /outbreaks/nearby — Retrieve active disease outbreak clusters near lat/lon."""
    prefix = geo_service.encode(lat, lon, precision=5)
    search_geohashes = geo_service.get_adjacent_cells(prefix)

    raw_obs = await firestore_service.get_observations_in_geohashes(search_geohashes)
    clusters = clustering_service.cluster_observations(raw_obs)

    if not clusters:
        # Return default mock cluster if no live DBSCAN clusters formed yet
        clusters = [MOCK_OUTBREAK]

    return clusters
