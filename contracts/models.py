from datetime import datetime
from pydantic import BaseModel


class PlotPassport(BaseModel):
    plot_id: str                    # deterministic hash of geohash
    lat: float
    lon: float
    geohash: str                    # 7 chars — this is our spatial index
    district: str
    state: str
    ndvi_series: list[dict]         # [{"date": "2024-03-01", "value": 0.62}]
    inferred_crop: str
    crop_stage_days: int
    cropping_history: list[str]     # ["tomato", "tomato", "onion"]
    soil: dict                      # {"ph": 6.4, "soc": 0.51, "texture": "loam"}
    weather_10d: dict               # {"rh_avg": 87, "rain_mm": 42, "temp_max": 31}
    data_sources: list[str]         # provenance — needed for the DPG claim
    schema_version: str = "1.0"


class Diagnosis(BaseModel):
    disease_name: str
    confidence: float               # 0.0–1.0
    differentials: list[str]
    is_action_needed: bool          # False → the "don't spray" path
    action_text: str
    dosage: str | None
    estimated_cost_inr: int
    urgency_hours: int
    escalate_to_human: bool         # True when confidence < 0.65
    reasoning_context: list[str]    # ["RH >85% for 4 nights", "day 58 tomato"]
    # Both source lists are overwritten server-side after the model responds —
    # they record what was really retrieved, not what the model chose to write.
    # Keep them distinct: `sources` are reviewed ICAR documents and may back a
    # dosage; `web_sources` are pages Google Search returned and may not.
    sources: list[str]                    # ICAR filenames used by RAG
    web_sources: list[str] = []           # URLs from Gemini search grounding


class Outbreak(BaseModel):
    cluster_id: str
    disease: str
    centroid: tuple[float, float]
    radius_km: float
    report_count: int               # NEVER serialised if < 5
    distinct_plots: int             # must be >= 3
    first_seen: datetime
    alert_ring_km: float = 15.0
