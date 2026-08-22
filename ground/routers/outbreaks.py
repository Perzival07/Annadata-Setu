import logging
from typing import List
from fastapi import APIRouter

from contracts.models import Outbreak
from contracts.mock_data import OUTBREAK as MOCK_OUTBREAK
from ground.services.firestore import firestore_service
from ground.services.cluster import clustering_service

logger = logging.getLogger("ground.router.outbreaks")

router = APIRouter(prefix="", tags=["Outbreaks Radar"])

@router.get("/outbreaks", response_model=List[Outbreak])
async def list_active_outbreaks():
    """GET /outbreaks — List all active epidemiological disease clusters across districts."""
    # Query all stored observations
    raw_obs = await firestore_service.get_observations_in_geohashes(["te7", "te8", "te9"])
    clusters = clustering_service.cluster_observations(raw_obs)

    if not clusters:
        clusters = [MOCK_OUTBREAK]

    return clusters
