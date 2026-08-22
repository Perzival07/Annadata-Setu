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
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{GROUND_URL}/plot-passport", json={"lat": lat, "lon": lon})
        res.raise_for_status()
        return PlotPassport(**res.json())

async def diagnose_leaf(image_url: str, passport: PlotPassport) -> Diagnosis:
    if MOCK:
        return mock_data.DIAGNOSIS
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{BRAIN_URL}/diagnose", json={"image_url": image_url, "passport": passport.model_dump()})
        res.raise_for_status()
        return Diagnosis(**res.json())

async def get_nearby_outbreaks(lat: float, lon: float) -> list[Outbreak]:
    if MOCK:
        return [mock_data.OUTBREAK]
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{GROUND_URL}/outbreaks/nearby", params={"lat": lat, "lon": lon})
        res.raise_for_status()
        return [Outbreak(**item) for item in res.json()]
