import os
import json
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from contracts.client import get_nearby_outbreaks
from contracts.constants import OUTBREAK_MIN_REPORTS, OUTBREAK_MIN_DISTINCT_PLOTS
from brain.services.registry import get_registered_models, get_model_by_id

logger = logging.getLogger("brain.router.public_api")

router = APIRouter(prefix="/api/v1", tags=["Public DPG API"])

@router.get("/outbreaks")
async def get_public_outbreaks(lat: Optional[float] = 19.9975, lon: Optional[float] = 73.7898):
    """
    Public GeoJSON endpoint listing anonymized disease outbreaks.
    Enforces k-anonymity: Clusters with report_count < 5 are NEVER returned.
    """
    try:
        outbreaks = await get_nearby_outbreaks(lat, lon)
    except Exception as e:
        # This feed is the DPG artifact — another state may consume it as fact.
        # Serving a fixture when the datastore is unreachable publishes an
        # epidemic that does not exist. An outage is a 503, not an outbreak.
        logger.error(f"Outbreak source unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail="Outbreak data source is temporarily unavailable.",
        )

    features = []
    for ob in outbreaks:
        # Enforce k-anonymity rule at API boundary
        if ob.report_count < OUTBREAK_MIN_REPORTS or ob.distinct_plots < OUTBREAK_MIN_DISTINCT_PLOTS:
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [ob.centroid[1], ob.centroid[0]]  # [lon, lat] for GeoJSON
            },
            "properties": {
                "cluster_id": ob.cluster_id,
                "disease": ob.disease,
                "radius_km": ob.radius_km,
                "alert_ring_km": ob.alert_ring_km,
                "first_seen": ob.first_seen.isoformat()
                # PII / exact report count is omitted for k-anonymity
            }
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "dpg_standard": "disease-observation.v1.jsonld",
            "k_anonymity_min_reports": OUTBREAK_MIN_REPORTS,
            "license": "Apache-2.0"
        }
    }

@router.get("/models")
def list_models():
    """Public Model Registry endpoint listing model weights, F1 scores, and fork lineage."""
    return {
        "models": get_registered_models(),
        "schema": "model-registry.v1.jsonld"
    }

@router.get("/models/{model_id}")
def get_model(model_id: str):
    """Retrieve specific model metadata and lineage."""
    model = get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@router.get("/schema/{schema_name}")
def get_schema(schema_name: str):
    """Serve DPG JSON-LD schema specification files."""
    # schema_name arrives from the URL. Joining it straight onto a path lets
    # "../../etc/passwd" out of the schema directory, so resolve and confirm
    # the result is still inside it.
    schema_dir = os.path.abspath("schema")
    for candidate in (f"{schema_name}.jsonld", schema_name):
        resolved = os.path.abspath(os.path.join(schema_dir, candidate))
        if os.path.commonpath([schema_dir, resolved]) != schema_dir:
            continue
        if os.path.isfile(resolved):
            with open(resolved, "r") as f:
                return JSONResponse(content=json.load(f))

    raise HTTPException(status_code=404, detail=f"Schema {schema_name} not found")
