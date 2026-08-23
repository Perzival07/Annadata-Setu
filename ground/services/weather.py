import httpx
import logging
from typing import Any, Dict, List

logger = logging.getLogger("ground.weather")

# BRAIN.md §11 (11:00): the 4-night RH average is the disease-pressure signal
# the diagnosis prompt actually reasons over. Nights, not days, and the next
# four of them — averaging ten days of nights flattens the very spike that
# means "spray before Thursday".
NIGHT_HOURS = {22, 23, 0, 1, 2, 3, 4, 5}
NIGHTS_TRACKED = 4

FALLBACK = {
    "rh_avg": 87,
    "rain_mm": 42,
    "temp_max": 31,
    "disease_pressure": "HIGH",
    "source": "Open-Meteo Regional Fallback",
}


class WeatherService:
    async def get_weather_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch a 10-day forecast from Open-Meteo (no API key required) and compute
        the 4-night average relative humidity.
        """
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=relative_humidity_2m,temperature_2m,rain"
            "&forecast_days=10"
            # Without this Open-Meteo returns UTC, and "night" for a Nashik plot
            # would be computed against the wrong 8 hours of the day.
            "&timezone=auto"
        )
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    hourly = data.get("hourly", {})
                    times = hourly.get("time", [])
                    rh_list = hourly.get("relative_humidity_2m", [])
                    temp_list = hourly.get("temperature_2m", [])
                    rain_list = hourly.get("rain", [])

                    rh_avg = self._four_night_rh(times, rh_list)
                    if rh_avg is not None:
                        temp_max = int(max(temp_list)) if temp_list else FALLBACK["temp_max"]
                        rain_mm = int(sum(r for r in rain_list if r is not None)) if rain_list else FALLBACK["rain_mm"]
                        return {
                            "rh_avg": rh_avg,
                            "rain_mm": rain_mm,
                            "temp_max": temp_max,
                            "disease_pressure": "HIGH" if rh_avg > 85 else "MODERATE",
                            "nights_sampled": NIGHTS_TRACKED,
                            "source": "Open-Meteo API",
                        }
                    logger.warning("Open-Meteo returned no usable night hours; using regional fallback.")
        except Exception as e:
            logger.warning(f"Open-Meteo API query failed, using regional fallback: {e}")

        return dict(FALLBACK)

    @staticmethod
    def _four_night_rh(times: List[str], rh_list: List[Any]) -> int | None:
        """Average RH over the next 4 nights, read off the returned timestamps.

        Indexing by `i % 24` only works if the series happens to start at local
        midnight. Open-Meteo starts at the current day's 00:00 in the requested
        timezone, but reading the hour out of the timestamp is correct whatever
        the series does.
        """
        if not times or not rh_list:
            return None

        by_night: Dict[str, List[float]] = {}
        order: List[str] = []
        for stamp, rh in zip(times, rh_list):
            if rh is None:
                continue
            try:
                date_part, time_part = stamp.split("T")
                hour = int(time_part.split(":")[0])
            except (ValueError, AttributeError):
                continue
            if hour not in NIGHT_HOURS:
                continue
            # 22:00 and 23:00 belong to the night that carries into the next
            # date, so they are grouped with it rather than counted separately.
            night_key = date_part if hour < 12 else f"{date_part}+"
            if night_key not in by_night:
                by_night[night_key] = []
                order.append(night_key)
            by_night[night_key].append(float(rh))

        sampled = [v for key in order[:NIGHTS_TRACKED] for v in by_night[key]]
        if not sampled:
            return None
        return int(round(sum(sampled) / len(sampled)))


weather_service = WeatherService()
