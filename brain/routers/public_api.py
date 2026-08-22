import os
import json
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from contracts.client import get_nearby_outbreaks
from contracts.mock_data import OUTBREAK as MOCK_OUTBREAK
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
    except Exception:
        outbreaks = [MOCK_OUTBREAK]

    features = []
    for ob in outbreaks:
        # Enforce k-anonymity rule at API boundary
        if ob.report_count < 5 or ob.distinct_plots < 3:
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
            "k_anonymity_min_reports": 5,
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
    schema_path = os.path.join("schema", f"{schema_name}.jsonld")
    if not os.path.exists(schema_path):
        schema_path = os.path.join("schema", f"{schema_name}")
    
    if not os.path.exists(schema_path):
        raise HTTPException(status_code=404, detail=f"Schema {schema_name} not found")

    with open(schema_path, "r") as f:
        return JSONResponse(content=json.load(f))
