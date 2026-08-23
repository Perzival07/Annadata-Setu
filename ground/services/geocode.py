"""Reverse geocoding — turn the farmer's dropped pin into a real district.

The district is not cosmetic. It selects the NDVI fallback curve
(earth_engine.py), the cropping-history prior (crop_infer.py), the soil
fallback, it is the field the outbreak radar groups by, and since the
multi-language work it also decides which language a farmer is answered in when
they have not told us. Until this module existed every plot was labelled from a
default argument — `district: str = "Nashik"` — so a farmer in Vidarbha got
Nashik's telemetry defaults and joined Nashik's cluster.

TWO PROVIDERS, AND WHY NOMINATIM IS THE DEFAULT
Google Maps Geocoding requires an API key and a billing account. That is a
reasonable ask for production and an unreasonable one for a clone-and-run, and
the failure mode of "no key" was the very bug above: everybody is in Nashik.
OpenStreetMap's Nominatim needs no key, no billing and no signup, and returns
`state_district` and `state` for Indian coordinates that match the names this
project already keys on. Verified against Nashik, Nagpur, Kolkata, Lucknow and
Kochi — districts and states all correct.

So: Nominatim by default, Google automatically when a key is present. Setting
GEOCODER forces one or disables lookups entirely.

Both are called over plain REST rather than a client library — one GET, and
ground/ already depends on httpx. Adding google-maps-services for this would be
a third auth path in a service that already carries Earth Engine and Firestore
credentials.

BEING A GOOD CITIZEN ON A FREE SERVICE
Nominatim's usage policy caps the public instance at one request per second and
requires a User-Agent that identifies the application; generic agents are
blocked outright. Both are honoured below. Real call volume is far under that
anyway — passports are cached by geohash for 7 days, so a lookup happens once
per new plot — but a demo that pins twenty farmers at once would burst without
the limiter.

No provider, no network, no match: return None and let the caller keep whatever
it already had. Guessing a district from coordinates is precisely the failure
this module exists to remove.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, NamedTuple, Optional, Tuple

import httpx

logger = logging.getLogger("ground.geocode")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# "nominatim" | "google" | "none" | "" (auto: google when keyed, else nominatim)
GEOCODER = os.getenv("GEOCODER", "").strip().lower()

GOOGLE_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"

# Nominatim blocks generic user agents. This must identify the application and
# stay honest about what it is.
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "AnnadataSetu/1.0 (+https://github.com/Perzival07/Annadata-Setu)",
)
# Their policy is one request per second. The margin is deliberate — being
# throttled costs us the district entirely.
NOMINATIM_MIN_INTERVAL_S = 1.1

# The passport aggregator already runs three telemetry fetches in parallel and
# is on the farmer's critical path. This one is small; it does not get to be slow.
TIMEOUT_S = 4.0

# Google's administrative_area_level_2 is the district in India, level_1 the
# state. Level 3 is the taluka — worth reading as a fallback, because a few
# rural pins come back without a level_2.
DISTRICT_TYPES = ("administrative_area_level_2", "administrative_area_level_3")
STATE_TYPE = "administrative_area_level_1"

# Nominatim's equivalents. state_district is the district proper; county is the
# fallback, which some rural pins carry instead.
NOMINATIM_DISTRICT_KEYS = ("state_district", "county")

SOURCE_GOOGLE = "Google Maps Geocoding API"
# ODbL requires attribution, and data_sources is exactly where it belongs — the
# DPG record then carries it to anyone consuming the feed.
SOURCE_NOMINATIM = "OpenStreetMap Nominatim (ODbL)"
# MOCK_MODE answers from the demo fixture without calling anything. It must say
# so: `source` is copied into PlotPassport.data_sources, which is the DPG audit
# trail, and naming an API that was never contacted is exactly the uncheckable
# provenance this project has already had to remove once.
SOURCE_MOCK = "Demo fixture (MOCK_MODE)"

# Suffixes Google and Nominatim append that our district tables do not use.
_DISTRICT_SUFFIXES = (" District", " Subdistrict", " district")


class GeocodePlace(NamedTuple):
    district: str
    state: str
    source: str  # what actually produced this, for data_sources


# Nashik, the demo district (BRAIN.md §13).
MOCK_RESULT = GeocodePlace("Nashik", "Maharashtra", SOURCE_MOCK)


def active_provider() -> Optional[str]:
    """Which provider will actually be used: 'google', 'nominatim' or None."""
    if GEOCODER == "none":
        return None
    if GEOCODER == "google":
        return "google" if API_KEY else None
    if GEOCODER == "nominatim":
        return "nominatim"
    # Auto: a key means someone paid for the better service, so use it.
    return "google" if API_KEY else "nominatim"


def _clean(name: Optional[str]) -> Optional[str]:
    """'Nashik District' -> 'Nashik', so it matches contracts/constants.py."""
    if not name:
        return None
    cleaned = name.strip()
    for suffix in _DISTRICT_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned or None


def _component(result: Dict[str, Any], wanted: Tuple[str, ...]) -> Optional[str]:
    """First Google address component matching any of `wanted`, in preference order."""
    components = result.get("address_components") or []
    for want in wanted:
        for component in components:
            if want in (component.get("types") or []):
                name = _clean(component.get("long_name"))
                if name:
                    return name
    return None


class _RateLimiter:
    """One-request-per-interval gate, shared across concurrent passport builds."""

    def __init__(self, interval: float):
        self.interval = interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self):
        async with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last = time.monotonic()


class GeocodeService:
    def __init__(self):
        self._nominatim_gate = _RateLimiter(NOMINATIM_MIN_INTERVAL_S)

    async def reverse(self, lat: float, lon: float) -> Optional[GeocodePlace]:
        """Where a coordinate is, or None if it cannot be resolved."""
        if MOCK:
            return MOCK_RESULT

        provider = active_provider()
        if provider is None:
            logger.info(
                "Geocoding disabled (GEOCODER=none, or GEOCODER=google with no key) — "
                "keeping the caller's district rather than looking one up."
            )
            return None

        if provider == "google":
            return await self._reverse_google(lat, lon)
        return await self._reverse_nominatim(lat, lon)

    # ------------------------------------------------------------------ Google

    async def _reverse_google(self, lat: float, lon: float) -> Optional[GeocodePlace]:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                res = await client.get(
                    GOOGLE_ENDPOINT,
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
            logger.warning(f"Google reverse geocode of ({lat}, {lon}) failed: {e}")
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

        logger.info(f"Reverse geocoded ({lat}, {lon}) to {district}, {state} via Google.")
        # A district without a state is still worth having; the state is only
        # ever displayed — though the language layer reads it, so prefer having it.
        return GeocodePlace(district, state or "", SOURCE_GOOGLE)

    # --------------------------------------------------------------- Nominatim

    async def _reverse_nominatim(self, lat: float, lon: float) -> Optional[GeocodePlace]:
        try:
            await self._nominatim_gate.wait()
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                res = await client.get(
                    NOMINATIM_ENDPOINT,
                    params={
                        "lat": lat,
                        "lon": lon,
                        "format": "jsonv2",
                        # zoom=10 is administrative-area detail. Higher zooms
                        # return the street, which we would only throw away.
                        "zoom": 10,
                        "addressdetails": 1,
                        "accept-language": "en",
                    },
                    headers={"User-Agent": NOMINATIM_USER_AGENT},
                )
                res.raise_for_status()
                payload = res.json()
        except Exception as e:
            logger.warning(f"Nominatim reverse geocode of ({lat}, {lon}) failed: {e}")
            return None

        if payload.get("error"):
            logger.info(f"Nominatim found nothing at ({lat}, {lon}): {payload['error']}")
            return None

        address = payload.get("address") or {}
        district = next(
            (_clean(address.get(key)) for key in NOMINATIM_DISTRICT_KEYS if address.get(key)),
            None,
        )
        state = _clean(address.get("state"))

        if not district:
            logger.info(f"Nominatim result for ({lat}, {lon}) carried no district.")
            return None

        logger.info(f"Reverse geocoded ({lat}, {lon}) to {district}, {state} via Nominatim.")
        return GeocodePlace(district, state or "", SOURCE_NOMINATIM)

    def status(self) -> Dict[str, Any]:
        provider = active_provider()
        return {
            "provider": provider or "disabled",
            # True whenever a lookup will actually happen — which, unlike before,
            # is now the default rather than something you configure.
            "configured": provider is not None,
            "needs_api_key": provider == "google",
            "mock": MOCK,
        }


geocode_service = GeocodeService()
