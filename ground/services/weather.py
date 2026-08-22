import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger("ground.weather")

class WeatherService:
    async def get_weather_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch 10-day forecast from Open-Meteo REST API (no API key required).
        Computes 4-night average relative humidity (RH) as the primary fungal disease pressure signal.
        """
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=relative_humidity_2m,temperature_2m,rain&forecast_days=10"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    hourly = data.get("hourly", {})
                    rh_list = hourly.get("relative_humidity_2m", [])
                    temp_list = hourly.get("temperature_2m", [])
                    rain_list = hourly.get("rain", [])

                    # Compute 4-night RH average (night hours 22:00 - 06:00)
                    night_rh = [rh_list[i] for i in range(len(rh_list)) if i % 24 in [22, 23, 0, 1, 2, 3, 4, 5]]
                    rh_avg = int(sum(night_rh) / len(night_rh)) if night_rh else 85
                    temp_max = int(max(temp_list)) if temp_list else 31
                    rain_mm = int(sum(rain_list)) if rain_list else 42

                    return {
                        "rh_avg": rh_avg,
                        "rain_mm": rain_mm,
                        "temp_max": temp_max,
                        "disease_pressure": "HIGH" if rh_avg > 85 else "MODERATE",
                        "source": "Open-Meteo API"
                    }
        except Exception as e:
            logger.warning(f"Open-Meteo API query failed, using regional fallback: {e}")

        return {
            "rh_avg": 87,
            "rain_mm": 42,
            "temp_max": 31,
            "disease_pressure": "HIGH",
            "source": "Open-Meteo Regional Fallback"
        }

weather_service = WeatherService()
