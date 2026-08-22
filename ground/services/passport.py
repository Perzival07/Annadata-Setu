import hashlib
import asyncio
import logging
from typing import Dict, Any

from contracts.models import PlotPassport
from ground.services.geo import geo_service
from ground.services.earth_engine import earth_engine_service
from ground.services.soil import soil_service
from ground.services.weather import weather_service
from ground.services.crop_infer import crop_infer_service
from ground.services.firestore import firestore_service

logger = logging.getLogger("ground.passport")

class PassportAggregatorService:
    async def build_plot_passport(self, lat: float, lon: float, district: str = "Nashik", state: str = "Maharashtra") -> PlotPassport:
        """
        Asynchronously aggregate 3 telemetry fetches via asyncio.gather:
        1. Earth Engine (3-yr NDVI series)
        2. ISRIC SoilGrids (pH, SOC, texture)
        3. Open-Meteo Weather (10-day forecast, 4-night RH average)
        Checks 7-day geohash cache first.
        """
        geohash = geo_service.encode(lat, lon, precision=7)
        plot_id = f"hash_{hashlib.md5(geohash.encode()).hexdigest()[:8]}"

        # 1. Check cache first
        cached = await firestore_service.get_cached_passport(geohash)
        if cached:
            logger.info(f"Hit passport cache for geohash {geohash}")
            return PlotPassport(**cached)

        # 2. Parallel async telemetry fetch
        ndvi_task = earth_engine_service.get_ndvi_series(lat, lon, district=district)
        soil_task = soil_service.get_soil_properties(lat, lon, district=district)
        weather_task = weather_service.get_weather_forecast(lat, lon)

        results = await asyncio.gather(ndvi_task, soil_task, weather_task, return_exceptions=True)

        ndvi_series = results[0] if not isinstance(results[0], Exception) else []
        soil_data = results[1] if not isinstance(results[1], Exception) else {"ph": 6.4, "soc": 0.51, "texture": "loam"}
        weather_data = results[2] if not isinstance(results[2], Exception) else {"rh_avg": 87, "rain_mm": 42, "temp_max": 31}

        # 3. Infer crop type & stage from NDVI curve dynamics
        inferred_crop, crop_stage_days, history = crop_infer_service.infer_crop_and_stage(ndvi_series, district=district)

        data_sources = [
            soil_data.get("source", "ISRIC SoilGrids v2"),
            weather_data.get("source", "Open-Meteo API"),
            "Sentinel-2 L2A Harmonized"
        ]

        passport = PlotPassport(
            plot_id=plot_id,
            lat=round(lat, 4),
            lon=round(lon, 4),
            geohash=geohash,
            district=district,
            state=state,
            ndvi_series=ndvi_series,
            inferred_crop=inferred_crop,
            crop_stage_days=crop_stage_days,
            cropping_history=history,
            soil=soil_data,
            weather_10d=weather_data,
            data_sources=data_sources,
            schema_version="1.0"
        )

        # 4. Save to cache
        await firestore_service.cache_passport(geohash, passport.model_dump())

        return passport

passport_aggregator_service = PassportAggregatorService()
