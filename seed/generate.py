import json
import random
from datetime import datetime, timezone, timedelta

def generate_seed_dataset():
    """
    Generate synthetic seed dataset according to BRAIN.md §11:
    - 1 hotspot cluster (7 reports in Nashik 5km cell)
    - 2 sub-threshold clusters of 3 (must not appear — proves k-anonymity)
    - 40 scattered reports
    - 42 silent plots in the 15km alert ring
    """
    observations = []

    # 1. Hotspot Cluster: 7 reports in 5km cell (Nashik)
    base_lat, base_lon = 19.9975, 73.7898
    for i in range(7):
        obs = {
            "obs_id": f"seed_hotspot_{i+1}",
            "plot_id": f"plot_nashik_hotspot_{i+1}",
            "geohash": "te7u23x",
            "lat": round(base_lat + (random.uniform(-0.01, 0.01)), 4),
            "lon": round(base_lon + (random.uniform(-0.01, 0.01)), 4),
            "district": "Nashik",
            "crop": "Tomato",
            "disease": "Early Blight",
            "confidence": round(random.uniform(0.82, 0.94), 2),
            "is_action_needed": True,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5))).isoformat()
        }
        observations.append(obs)

    # 2. Sub-threshold cluster 1: 3 reports (Vidarbha)
    for i in range(3):
        obs = {
            "obs_id": f"seed_sub1_{i+1}",
            "plot_id": f"plot_vidarbha_sub1_{i+1}",
            "geohash": "te8v91z",
            "lat": round(21.1458 + (random.uniform(-0.01, 0.01)), 4),
            "lon": round(79.0882 + (random.uniform(-0.01, 0.01)), 4),
            "district": "Vidarbha",
            "crop": "Cotton",
            "disease": "Bacterial Blight",
            "confidence": round(random.uniform(0.75, 0.88), 2),
            "is_action_needed": True,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        }
        observations.append(obs)

    # 3. Sub-threshold cluster 2: 3 reports (Pune)
    for i in range(3):
        obs = {
            "obs_id": f"seed_sub2_{i+1}",
            "plot_id": f"plot_pune_sub2_{i+1}",
            "geohash": "tek312a",
            "lat": round(18.5204 + (random.uniform(-0.01, 0.01)), 4),
            "lon": round(73.8567 + (random.uniform(-0.01, 0.01)), 4),
            "district": "Pune",
            "crop": "Onion",
            "disease": "Purple Blotch",
            "confidence": round(random.uniform(0.78, 0.90), 2),
            "is_action_needed": True,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        }
        observations.append(obs)

    # 4. 40 Scattered observations
    for i in range(40):
        obs = {
            "obs_id": f"seed_scattered_{i+1}",
            "plot_id": f"plot_scattered_{i+1}",
            "geohash": f"geohash_sc_{i}",
            "lat": round(random.uniform(18.0, 21.5), 4),
            "lon": round(random.uniform(73.0, 79.5), 4),
            "district": random.choice(["Nashik", "Vidarbha", "Pune", "Satara"]),
            "crop": random.choice(["Tomato", "Onion", "Cotton", "Soybean"]),
            "disease": random.choice(["Early Blight", "Late Blight", "Nitrogen Deficiency"]),
            "confidence": round(random.uniform(0.60, 0.95), 2),
            "is_action_needed": random.choice([True, False]),
            "created_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 6))).isoformat()
        }
        observations.append(obs)

    # Write observations.json
    with open("seed/observations.json", "w") as f:
        json.dump(observations, f, indent=2)

    # 5. Generate 42 Silent Plots in the 15km Alert Ring
    ring_plots = []
    for i in range(42):
        plot = {
            "plot_id": f"plot_silent_ring_{i+1}",
            "farmer_phone": f"9198765{i+1000:05d}",
            "lat": round(base_lat + (random.uniform(-0.12, 0.12)), 4),
            "lon": round(base_lon + (random.uniform(-0.12, 0.12)), 4),
            "district": "Nashik",
            "inferred_crop": "Tomato"
        }
        ring_plots.append(plot)

    # Write plots.json
    with open("seed/plots.json", "w") as f:
        json.dump(ring_plots, f, indent=2)

    print(f"Seed generator complete: {len(observations)} observations and {len(ring_plots)} silent ring plots generated.")

if __name__ == "__main__":
    generate_seed_dataset()
