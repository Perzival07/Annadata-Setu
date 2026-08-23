import os
import httpx
from contracts import mock_data
from contracts.models import PlotPassport, Diagnosis, Outbreak

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
GROUND_URL = os.getenv("GROUND_URL", "http://localhost:8003")
BRAIN_URL = os.getenv("BRAIN_URL", "http://localhost:8002")

async def get_plot_passport(lat: float, lon: float) -> PlotPassport:
    if MOCK:
        return mock_data.PASSPORT
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(f"{GROUND_URL}/plot-passport", json={"lat": lat, "lon": lon})
        res.raise_for_status()
        return PlotPassport(**res.json())

async def diagnose_leaf(
    image_url: str | None,
    passport: PlotPassport,
    image_base64: str | None = None,
) -> Diagnosis:
    """Ask brain to diagnose a leaf.

    `image_base64` is the path that actually works for WhatsApp media: Meta's
    graph URLs need our bearer token, so brain cannot fetch them itself. The
    caller downloads the bytes and passes them through. `image_url` remains for
    publicly reachable images.
    """
    if MOCK:
        return mock_data.DIAGNOSIS
    payload = {"passport": passport.model_dump()}
    if image_base64:
        payload["image_base64"] = image_base64
    if image_url:
        payload["image_url"] = image_url
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{BRAIN_URL}/diagnose", json=payload)
        res.raise_for_status()
        return Diagnosis(**res.json())

async def get_nearby_outbreaks(lat: float, lon: float) -> list[Outbreak]:
    if MOCK:
        return [mock_data.OUTBREAK]
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(f"{GROUND_URL}/outbreaks/nearby", params={"lat": lat, "lon": lon})
        res.raise_for_status()
        return [Outbreak(**item) for item in res.json()]


async def compose_marathi_script(diagnosis: Diagnosis, passport: PlotPassport | None = None) -> str | None:
    """Ask brain for the spoken Marathi advisory.

    Returns None when unavailable — the caller must then use its own
    Marathi-only template rather than speaking a part-English script.
    """
    if MOCK:
        return None
    payload = {"diagnosis": diagnosis.model_dump()}
    if passport:
        payload["passport"] = passport.model_dump()
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(f"{BRAIN_URL}/advisory-script", json=payload)
        res.raise_for_status()
        return res.json().get("script")
