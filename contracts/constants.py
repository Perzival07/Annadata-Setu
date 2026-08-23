"""Shared constants for Annadata Setu."""

DISTRICTS = ["Nashik", "Vidarbha", "Pune", "Ahmednagar", "Satara"]
# The crops brain/services/rag.py carries built-in agronomic notes for, plus
# Soybean which the rotation advisor recommends. Ordered roughly by area sown in
# the subcontinent: rice and wheat first, then the coarse cereal, the fibre and
# cash crops, the major pulses and oilseeds, and finally the horticultural crops
# this project started with.
CROPS = [
    "Rice", "Wheat", "Maize",
    "Cotton", "Sugarcane",
    "Chickpea", "Pigeon Pea", "Soybean",
    "Mustard", "Groundnut",
    "Potato", "Tomato", "Onion",
]

OUTBREAK_MIN_REPORTS = 5
OUTBREAK_MIN_DISTINCT_PLOTS = 3
OUTBREAK_WINDOW_DAYS = 7
ALERT_RING_KM = 15.0
