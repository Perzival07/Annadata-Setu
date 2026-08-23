import hashlib
import asyncio
import logging
from typing import Optional, Tuple

from contracts.models import PlotPassport
from ground.services.geo import geo_service
from ground.services.geocode import geocode_service
from ground.services.earth_engine import earth_engine_service
from ground.services.soil import soil_service
from ground.services.weather import weather_service
from ground.services.crop_infer import crop_infer_service
from ground.services.firestore import firestore_service

logger = logging.getLogger("ground.passport")

# Where the demo is set (BRAIN.md §13). Used only when the pin cannot be
# resolved to a real district and the caller named none.
DEFAULT_DISTRICT, DEFAULT_STATE = "Nashik", "Maharashtra"


class PassportAggregatorService:
    async def build_plot_passport(
        self,
        lat: float,
        lon: float,
        district: Optional[str] = None,
        state: Optional[str] = None,
    ) -> PlotPassport:
        """
        Asynchronously aggregate 3 telemetry fetches via asyncio.gather:
        1. Earth Engine (3-yr NDVI series)
        2. ISRIC SoilGrids (pH, SOC, texture)
        3. Open-Meteo Weather (10-day forecast, 4-night RH average)
        Checks 7-day geohash cache first.

        `district` defaults to None so the pin decides. It used to default to
        "Nashik", which meant a farmer anywhere else was labelled Nashik, given
        Nashik's telemetry fallbacks and clustered into Nashik's outbreaks.
        """
        geohash = geo_service.encode(lat, lon, precision=7)
        plot_id = f"hash_{hashlib.md5(geohash.encode()).hexdigest()[:8]}"

        # 1. Check cache first
        cached = await firestore_service.get_cached_passport(geohash)
        if cached:
            logger.info(f"Hit passport cache for geohash {geohash}")
            return PlotPassport(**cached)

        # 2. Resolve where this pin actually is. Ahead of the telemetry fetch
        # rather than beside it, because district selects the NDVI, soil and
        # cropping-history fallbacks those calls use. It is skipped outright
        # when the caller named a district or no Maps key is configured, and
        # everything past here is behind the geohash cache.
        district, state, place_source = await self._resolve_place(lat, lon, district, state)

        # 3. Parallel async telemetry fetch
        ndvi_task = earth_engine_service.get_ndvi_series(lat, lon, district=district)
        soil_task = soil_service.get_soil_properties(lat, lon, district=district)
        weather_task = weather_service.get_weather_forecast(lat, lon)

        results = await asyncio.gather(ndvi_task, soil_task, weather_task, return_exceptions=True)

        ndvi_series = results[0] if not isinstance(results[0], Exception) else []
        soil_data = results[1] if not isinstance(results[1], Exception) else {"ph": 6.4, "soc": 0.51, "texture": "loam"}
        weather_data = results[2] if not isinstance(results[2], Exception) else {"rh_avg": 87, "rain_mm": 42, "temp_max": 31}

        # 4. Infer crop type & stage from NDVI curve dynamics
        inferred_crop, crop_stage_days, history = crop_infer_service.infer_crop_and_stage(ndvi_series, district=district)

        data_sources = [
            soil_data.get("source", "ISRIC SoilGrids v2"),
            weather_data.get("source", "Open-Meteo API"),
            "Sentinel-2 L2A Harmonized"
        ]
        # Provenance is the DPG claim (BRAIN.md §16) — if the district was looked
        # up rather than asserted by the caller, that is part of the record. The
        # label comes from whatever resolved it, so MOCK_MODE cannot credit an
        # API it never called.
        if place_source:
            data_sources.append(place_source)

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

        # 5. Save to cache
        await firestore_service.cache_passport(geohash, passport.model_dump())

        return passport

    async def _resolve_place(
        self,
        lat: float,
        lon: float,
        district: Optional[str],
        state: Optional[str],
    ) -> Tuple[str, str, Optional[str]]:
        """(district, state, provenance) for a pin.

        `provenance` is None when nothing looked the pin up — a district the
        caller asserted, or the Nashik fallback. It is a label only when
        something actually resolved it, and that label is whatever resolved it.

        A district the caller named wins: /plot-passport is also driven by the
        officer dashboard, which already knows which district it is looking at.
        """
        if district:
            return district, state or DEFAULT_STATE, None

        place = await geocode_service.reverse(lat, lon)
        if place:
            return place.district, place.state or DEFAULT_STATE, place.source

        logger.warning(
            f"Could not resolve a district for ({lat}, {lon}); falling back to "
            f"{DEFAULT_DISTRICT}. Its telemetry fallbacks and outbreak grouping "
            f"will be wrong if this plot is not there."
        )
        return DEFAULT_DISTRICT, state or DEFAULT_STATE, None


passport_aggregator_service = PassportAggregatorService()
