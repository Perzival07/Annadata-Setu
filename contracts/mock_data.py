from datetime import datetime, timezone
from contracts.models import PlotPassport, Diagnosis, Outbreak

PASSPORT = PlotPassport(
    plot_id="hash_te7u23",
    lat=19.9975,
    lon=73.7898,
    geohash="te7u23x",
    district="Nashik",
    state="Maharashtra",
    ndvi_series=[
        {"date": "2024-02-01", "value": 0.35},
        {"date": "2024-02-15", "value": 0.52},
        {"date": "2024-03-01", "value": 0.68},
    ],
    inferred_crop="Tomato",
    crop_stage_days=58,
    cropping_history=["Tomato", "Tomato", "Onion"],
    soil={"ph": 6.4, "soc": 0.51, "texture": "loam"},
    weather_10d={"rh_avg": 87, "rain_mm": 42, "temp_max": 31},
    data_sources=["Sentinel-2 L2A", "ISRIC SoilGrids v2", "Open-Meteo API"],
    schema_version="1.0"
)

DIAGNOSIS = Diagnosis(
    disease_name="Early Blight (Alternaria solani)",
    confidence=0.88,
    differentials=["Late Blight", "Septoria Leaf Spot"],
    is_action_needed=True,
    action_text="Spray Mancozeb 75% WP tomorrow morning before expected rain on Thursday.",
    dosage="2g per litre of water",
    estimated_cost_inr=340,
    urgency_hours=24,
    escalate_to_human=False,
    reasoning_context=["RH >85% for 4 nights", "day 58 tomato plot", "Abundant foliage stage"],
    sources=["ICAR_Tomato_Package_of_Practices_2023.pdf"]
)

OUTBREAK = Outbreak(
    cluster_id="cluster_nashik_eb_01",
    disease="Early Blight",
    centroid=(19.9975, 73.7898),
    radius_km=2.4,
    report_count=7,
    distinct_plots=5,
    first_seen=datetime.now(timezone.utc),
    alert_ring_km=15.0
)
