"""Reverse geocoding — turn the farmer's dropped pin into a real district.

The district is not cosmetic. It selects the NDVI fallback curve
(earth_engine.py), the cropping-history prior (crop_infer.py), the soil
fallback, and it is the field the outbreak radar groups by. Until now every
plot was labelled from a default argument: `district: str = "Nashik"` threaded
through passport.py and the /plot-passport request model. A farmer in Vidarbha
dropping a pin got Nashik telemetry defaults and their observation joined the
Nashik cluster.

Google Maps Geocoding is called over REST rather than through a client library —
one authenticated GET, and ground/ already depends on httpx. Adding
google-maps-services just for this would be a third auth path in a service that
already carries Earth Engine and Firestore credentials.

No key, no network, no match: return None and let the caller keep whatever it
already had. Guessing a district from coordinates is precisely the failure this
module exists to remove.
"""

import logging
import os
from typing import Any, Dict, NamedTuple, Optional, Tuple

import httpx

logger = logging.getLogger("ground.geocode")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"

# The passport aggregator already runs three telemetry fetches in parallel and
# is on the farmer's critical path. This one is small; it does not get to be slow.
TIMEOUT_S = 4.0

# Google's administrative_area_level_2 is the district in India, level_1 the
# state. Level 3 is the taluka — worth reading as a fallback, because a few
# rural pins come back without a level_2.
DISTRICT_TYPES = ("administrative_area_level_2", "administrative_area_level_3")
STATE_TYPE = "administrative_area_level_1"

SOURCE_LIVE = "Google Maps Geocoding API"
# MOCK_MODE answers from the demo fixture without calling anything. It must say
# so: `source` is copied into PlotPassport.data_sources, which is the DPG audit
# trail, and naming an API that was never contacted is exactly the uncheckable
# provenance this project has already had to remove once.
SOURCE_MOCK = "Demo fixture (MOCK_MODE)"


class GeocodePlace(NamedTuple):
    district: str
    state: str
    source: str  # what actually produced this, for data_sources


# Nashik, the demo district (BRAIN.md §13).
MOCK_RESULT = GeocodePlace("Nashik", "Maharashtra", SOURCE_MOCK)


def _component(result: Dict[str, Any], wanted: Tuple[str, ...]) -> Optional[str]:
    """First address component matching any of `wanted`, in preference order."""
    components = result.get("address_components") or []
    for want in wanted:
        for component in components:
            if want in (component.get("types") or []):
                name = (component.get("long_name") or "").strip()
                if name:
                    # "Nashik District" / "Pune District" -> "Nashik" / "Pune",
                    # so it matches contracts/constants.py DISTRICTS and the
                    # district keys the fallback tables are written against.
                    return name.removesuffix(" District").strip()
    return None


class GeocodeService:
    async def reverse(self, lat: float, lon: float) -> Optional[GeocodePlace]:
        """Where a coordinate is, or None if it cannot be resolved."""
        if MOCK:
            return MOCK_RESULT

        if not API_KEY:
            logger.info(
                "GOOGLE_MAPS_API_KEY unset — keeping the caller's district rather "
                "than looking one up."
            )
            return None

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                res = await client.get(
                    ENDPOINT,
                    params={
                        "latlng": f"{lat},{lon}",
                        "key": API_KEY,
                        # Ask for the administrative levels directly instead of
                        # paging through street addresses and plus codes.
                        "result_type": "administrative_area_level_2|administrative_area_level_1",
                        "language": "en",
                    },
                )
                res.raise_for_status()
                payload = res.json()
        except Exception as e:
            logger.warning(f"Reverse geocode of ({lat}, {lon}) failed: {e}")
            return None

        status = payload.get("status")
        if status == "ZERO_RESULTS":
            logger.info(f"No administrative area for ({lat}, {lon}) — likely offshore.")
            return None
        if status != "OK":
            # REQUEST_DENIED / OVER_QUERY_LIMIT are operator problems, and the
            # error_message is the only thing that says which.
            logger.warning(
                f"Geocoding API returned {status}: {payload.get('error_message', 'no detail')}"
            )
            return None

        district = state = None
        for result in payload.get("results") or []:
            district = district or _component(result, DISTRICT_TYPES)
            state = state or _component(result, (STATE_TYPE,))
            if district and state:
                break

        if not district:
            logger.info(f"Geocode for ({lat}, {lon}) carried no district component.")
            return None

        logger.info(f"Reverse geocoded ({lat}, {lon}) to {district}, {state}.")
        # A district without a state is still worth having; the state is only
        # ever displayed.
        return GeocodePlace(district, state or "", SOURCE_LIVE)

    def status(self) -> Dict[str, Any]:
        return {"configured": bool(API_KEY), "mock": MOCK}


geocode_service = GeocodeService()
