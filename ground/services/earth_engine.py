import os
import json
import asyncio
import logging
from datetime import date, timedelta
from typing import Dict, List

logger = logging.getLogger("ground.earth_engine")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

# BRAIN.md §11 (09:15): 150 m buffer ≈ 7 ha, three years of history.
PLOT_BUFFER_M = 150
HISTORY_YEARS = 3
# Sentinel-2 SR Harmonized scene classification values that are not usable
# ground: cloud shadow, medium/high cloud probability, cirrus, snow.
SCL_MASKED_CLASSES = [3, 8, 9, 10, 11]

# Last-resort curve if both Earth Engine and the district export are unavailable.
BASELINE_SERIES = [
    {"date": "2023-11-01", "value": 0.22},
    {"date": "2023-12-01", "value": 0.45},
    {"date": "2024-01-01", "value": 0.68},
    {"date": "2024-02-01", "value": 0.74},
    {"date": "2024-03-01", "value": 0.62},
]


class EarthEngineService:
    def __init__(self):
        self.ee = None
        self._init_ee()

    def _init_ee(self):
        if MOCK:
            logger.info("EarthEngineService initialized in MOCK_MODE.")
            return

        try:
            import ee
            ee.Initialize()
            self.ee = ee
            logger.info("Google Earth Engine API initialized successfully.")
        except Exception as e:
            logger.warning(f"Earth Engine initialization fallback: {e}")

    async def get_ndvi_series(self, lat: float, lon: float, district: str = "Nashik") -> List[Dict[str, float]]:
        """Fetch a 3-year Sentinel-2 NDVI time series for the plot's 150 m buffer."""
        if self.ee:
            try:
                # getInfo() blocks for 4-8s and must never sit on the event loop
                # (BRAIN.md §11) — the passport aggregator gathers three of these.
                series = await asyncio.to_thread(self._fetch_series_blocking, lat, lon)
                if series:
                    return series
                logger.warning("Earth Engine returned no cloud-free scenes; using district fallback.")
            except Exception as e:
                logger.warning(f"Earth Engine query failed, using district fallback: {e}")

        return self._fallback_series(district)

    # ------------------------------------------------------------------------

    def _fetch_series_blocking(self, lat: float, lon: float) -> List[Dict[str, float]]:
        ee = self.ee
        point = ee.Geometry.Point([lon, lat])
        buffer_area = point.buffer(PLOT_BUFFER_M)

        end = date.today()
        start = end - timedelta(days=365 * HISTORY_YEARS)

        def mask_clouds(image):
            """Cloud masking is not optional in monsoon India (BRAIN.md §11).

            Without it the NDVI series is a record of cloud brightness, and the
            crop-stage inference downstream reads those spikes as growth.
            """
            scl = image.select("SCL")
            mask = scl.neq(SCL_MASKED_CLASSES[0])
            for cls in SCL_MASKED_CLASSES[1:]:
                mask = mask.And(scl.neq(cls))
            return image.updateMask(mask)

        def add_ndvi(image):
            return image.addBands(image.normalizedDifference(["B8", "B4"]).rename("ndvi"))

        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(buffer_area)
            .filterDate(start.isoformat(), end.isoformat())
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .map(mask_clouds)
            .map(add_ndvi)
        )

        def to_feature(image):
            # reduceRegion is an Image method. The previous code called
            # reduceRegions on the ImageCollection, which raises every time —
            # the Earth Engine path could never have returned data.
            stats = image.select("ndvi").reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer_area,
                scale=10,
                maxPixels=int(1e9),
            )
            return ee.Feature(
                None,
                {"date": image.date().format("YYYY-MM-dd"), "ndvi": stats.get("ndvi")},
            )

        features = (
            ee.FeatureCollection(collection.map(to_feature))
            .filter(ee.Filter.notNull(["ndvi"]))
            .sort("date")
            .getInfo()
        )

        series = []
        for f in features.get("features", []):
            props = f.get("properties", {})
            value = props.get("ndvi")
            if value is None:
                continue
            series.append({"date": props.get("date"), "value": round(float(value), 3)})
        return series

    @staticmethod
    def _fallback_series(district: str) -> List[Dict[str, float]]:
        """Pre-exported district curves — the Earth Engine outage insurance."""
        fallback_file = os.path.join("seed", "ndvi_fallback", f"{district.lower()}.json")
        if os.path.exists(fallback_file):
            try:
                with open(fallback_file, "r") as f:
                    data = json.load(f)
                if data.get("ndvi_series"):
                    logger.info(f"Using pre-exported NDVI fallback for {district}.")
                    return data["ndvi_series"]
            except Exception as e:
                logger.warning(f"Could not read NDVI fallback {fallback_file}: {e}")

        return list(BASELINE_SERIES)


earth_engine_service = EarthEngineService()
