"""Designed seed dataset for the outbreak radar (BRAIN.md §11, 19:00).

Designed, not randomised: the shape of this data IS the demo. One hotspot that
must surface, two sub-threshold clusters that must NOT (the k-anonymity proof),
scattered noise, and exactly 42 silent plots inside the 15 km ring.

A fixed RNG seed keeps every rehearsal identical — a demo whose numbers move
between runs cannot be narrated.
"""

import json
import math
import os
import random
from datetime import datetime, timedelta, timezone

from ground.services.geo import geo_service

RANDOM_SEED = 20240315

NASHIK = (19.9975, 73.7898)
VIDARBHA = (21.1458, 79.0882)
PUNE = (18.5204, 73.8567)

HOTSPOT_REPORTS = 7          # >= 5, so it surfaces
SUB_THRESHOLD_REPORTS = 3    # < 5, so it must never surface
SCATTERED_REPORTS = 40
RING_PLOTS = 42              # the demo punchline — this number is spoken aloud

ALERT_RING_KM = 15.0
# Ring plots sit clear of the hotspot itself: they are the farmers who reported
# nothing, not the ones already infected.
RING_INNER_KM = 3.0
RING_OUTER_KM = 14.0

KM_PER_DEG_LAT = 111.32


def _offset_km(lat, lon, distance_km, bearing_deg):
    """Move a fixed number of km from a point along a bearing."""
    d_lat = distance_km * math.cos(math.radians(bearing_deg)) / KM_PER_DEG_LAT
    d_lon = distance_km * math.sin(math.radians(bearing_deg)) / (
        KM_PER_DEG_LAT * math.cos(math.radians(lat))
    )
    return round(lat + d_lat, 5), round(lon + d_lon, 5)


def _observation(rng, obs_id, plot_id, lat, lon, district, crop, disease, days_ago, conf_range):
    return {
        "obs_id": obs_id,
        "plot_id": plot_id,
        # A real geohash for the actual coordinates. Placeholder strings like
        # "geohash_sc_7" match no prefix range, so those observations were
        # invisible to every spatial query that reads this file.
        "geohash": geo_service.encode(lat, lon, precision=7),
        "lat": lat,
        "lon": lon,
        "district": district,
        "crop": crop,
        "disease": disease,
        "confidence": round(rng.uniform(*conf_range), 2),
        "is_action_needed": True,
        # Clustering drops undated observations, and only looks back 7 days.
        "created_at": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(),
    }


def generate_seed_dataset(out_dir="seed"):
    rng = random.Random(RANDOM_SEED)
    observations = []

    # 1. Hotspot: 7 reports inside one 5 km cell, spread over 6 days so the
    #    cluster reads as growing rather than as a single-day artefact.
    for i in range(HOTSPOT_REPORTS):
        lat, lon = _offset_km(*NASHIK, distance_km=rng.uniform(0.2, 2.0), bearing_deg=rng.uniform(0, 360))
        observations.append(_observation(
            rng, f"seed_hotspot_{i+1}", f"plot_nashik_hotspot_{i+1}",
            lat, lon, "Nashik", "Tomato", "Early Blight",
            days_ago=6 - i if i < 6 else 1, conf_range=(0.82, 0.94),
        ))

    # 2 & 3. Sub-threshold clusters — 3 reports each. These must not appear in
    #        any outbreak response; that absence is the k-anonymity proof.
    for label, centre, district, crop, disease in [
        ("sub1", VIDARBHA, "Vidarbha", "Cotton", "Bacterial Blight"),
        ("sub2", PUNE, "Pune", "Onion", "Purple Blotch"),
    ]:
        for i in range(SUB_THRESHOLD_REPORTS):
            lat, lon = _offset_km(*centre, distance_km=rng.uniform(0.2, 1.5), bearing_deg=rng.uniform(0, 360))
            observations.append(_observation(
                rng, f"seed_{label}_{i+1}", f"plot_{district.lower()}_{label}_{i+1}",
                lat, lon, district, crop, disease,
                days_ago=rng.randint(2, 5), conf_range=(0.75, 0.90),
            ))

    # 4. Scattered noise across Maharashtra — far enough apart that DBSCAN
    #    treats them as noise rather than accidentally forming a second cluster.
    for i in range(SCATTERED_REPORTS):
        lat = round(rng.uniform(18.0, 21.5), 5)
        lon = round(rng.uniform(73.0, 79.5), 5)
        observations.append(_observation(
            rng, f"seed_scattered_{i+1}", f"plot_scattered_{i+1}",
            lat, lon,
            rng.choice(["Nashik", "Vidarbha", "Pune", "Satara"]),
            rng.choice(["Tomato", "Onion", "Cotton", "Soybean"]),
            rng.choice(["Early Blight", "Late Blight", "Nitrogen Deficiency"]),
            days_ago=rng.randint(1, 6), conf_range=(0.60, 0.95),
        ))

    # 5. 42 silent plots, every one of them genuinely inside the 15 km ring.
    #    Scattering them in a lat/lon square put the corners ~18 km out, so the
    #    ring query returned 37 and the spoken "forty-two farmers" was wrong.
    ring_plots = []
    for i in range(RING_PLOTS):
        # Even bearings with a jittered radius: uniform coverage, no clumping.
        bearing = (360.0 / RING_PLOTS) * i + rng.uniform(-3, 3)
        distance = rng.uniform(RING_INNER_KM, RING_OUTER_KM)
        lat, lon = _offset_km(*NASHIK, distance_km=distance, bearing_deg=bearing)
        ring_plots.append({
            "plot_id": f"plot_silent_ring_{i+1}",
            "farmer_phone": f"9198765{i+1000:05d}",
            "lat": lat,
            "lon": lon,
            "geohash": geo_service.encode(lat, lon, precision=7),
            "district": "Nashik",
            "inferred_crop": "Tomato",
            "distance_from_hotspot_km": round(distance, 2),
        })

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "observations.json"), "w") as f:
        json.dump(observations, f, indent=2)
    with open(os.path.join(out_dir, "plots.json"), "w") as f:
        json.dump(ring_plots, f, indent=2)

    print(f"Seed complete: {len(observations)} observations, {len(ring_plots)} silent ring plots.")
    return observations, ring_plots


if __name__ == "__main__":
    generate_seed_dataset()
