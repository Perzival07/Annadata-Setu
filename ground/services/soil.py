import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger("ground.soil")

class SoilService:
    async def get_soil_properties(self, lat: float, lon: float, district: str = "Nashik") -> Dict[str, Any]:
        """
        Fetch soil composition from ISRIC SoilGrids REST API v2.

        SoilGrids returns integers scaled by a per-property d_factor of 10:
          phh2o  is pH*10      -> /10  gives pH
          soc    is dg/kg      -> /100 gives % organic carbon, the unit the
                                  passport and the agronomy prompts expect
        """
        url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&property=phh2o&property=soc"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    layers = data.get("properties", {}).get("layers", [])
                    ph, soc = 6.4, 0.51  # defaults
                    for layer in layers:
                        name = layer.get("name")
                        depths = layer.get("depths", [])
                        if depths:
                            mean_val = depths[0].get("values", {}).get("mean", 0)
                            if name == "phh2o":
                                ph = round(mean_val / 10.0, 1)
                            elif name == "soc":
                                soc = round(mean_val / 100.0, 2)

                    return {"ph": ph, "soc": soc, "texture": "clay loam", "source": "ISRIC SoilGrids v2.0"}
        except Exception as e:
            logger.warning(f"SoilGrids API query failed, using district average fallback: {e}")

        # District-average fallbacks
        district_soil_map = {
            "nashik": {"ph": 6.4, "soc": 0.51, "texture": "loam", "source": "District Soil Average"},
            "vidarbha": {"ph": 7.8, "soc": 0.42, "texture": "black cotton soil", "source": "District Soil Average"},
            "pune": {"ph": 6.8, "soc": 0.58, "texture": "silty clay", "source": "District Soil Average"}
        }
        return district_soil_map.get(district.lower(), {"ph": 6.5, "soc": 0.50, "texture": "loam", "source": "District Soil Average"})

soil_service = SoilService()
