import logging
from typing import List
from fastapi import APIRouter

from contracts.models import Outbreak
from contracts.mock_data import OUTBREAK as MOCK_OUTBREAK
from ground.services.firestore import firestore_service
from ground.services.cluster import clustering_service
from ground.services.geo import geo_service
from contracts.constants import ALERT_RING_KM

import os

logger = logging.getLogger("ground.router.outbreaks")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

router = APIRouter(prefix="", tags=["Outbreaks Radar"])

@router.get("/outbreaks", response_model=List[Outbreak])
async def list_active_outbreaks():
    """GET /outbreaks — List all active epidemiological disease clusters across districts."""
    raw_obs = await firestore_service.get_all_observations()
    clusters = clustering_service.cluster_observations(raw_obs)

    # This endpoint drives the scheduled ring-alert fan-out. An empty list means
    # "nobody gets warned today", which is the correct outcome when no cluster
    # crossed the k>=5 threshold. Only MOCK_MODE may substitute the fixture.
    if not clusters and MOCK:
        logger.info("MOCK_MODE=true — returning the fixture outbreak cluster.")
        return [MOCK_OUTBREAK]

    return clusters


@router.get("/alert-ring")
async def get_alert_ring(
    lat: float,
    lon: float,
    radius_km: float = ALERT_RING_KM,
    exclude_within_km: float = 0.0,
):
    """Plots inside an outbreak's alert ring — the fan-out target list.

    This is the "42 farmers who reported nothing just got warned" step
    (BRAIN.md §13). The scheduled radar used to skip it entirely and post a
    hardcoded list of three phone numbers to /push-alert.

    `exclude_within_km` drops the plots inside the cluster itself: they already
    have the disease, so a pre-emptive "act before it reaches you" is wrong.
    """
    plots = await firestore_service.get_registered_plots()

    in_ring = []
    for plot in plots:
        p_lat, p_lon = plot.get("lat"), plot.get("lon")
        if p_lat is None or p_lon is None:
            continue
        distance = geo_service.haversine_distance(lat, lon, p_lat, p_lon)
        if distance > radius_km or distance <= exclude_within_km:
            continue
        in_ring.append({
            "plot_id": plot.get("plot_id"),
            "farmer_phone": plot.get("farmer_phone"),
            "district": plot.get("district"),
            "inferred_crop": plot.get("inferred_crop"),
            "distance_km": round(distance, 2),
        })

    in_ring.sort(key=lambda p: p["distance_km"])
    districts = sorted({p["district"] for p in in_ring if p.get("district")})

    logger.info(f"Alert ring around ({lat}, {lon}) r={radius_km}km matched {len(in_ring)} plots.")
    return {
        "centroid": [lat, lon],
        "radius_km": radius_km,
        "plot_count": len(in_ring),
        "districts": districts,
        "plots": in_ring,
    }
