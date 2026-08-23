"""Ground service entrypoint (P3).

`.env` is loaded HERE, before any project import below. python-dotenv has been
in requirements.txt since the start but was never called, so a local
`uvicorn ...main:app` run read none of it — a key pasted into .env simply did
nothing, and the service reported itself healthy while answering every request
from its fallback path. docker-compose was unaffected: it passes .env through
`env_file`, which is why this stayed hidden.

The order matters and is not stylistic. Service modules read their configuration
at import time (`MOCK = os.getenv(...)` at module scope), so load_dotenv() has to
run before those imports, not merely before the app starts. Real environment
variables always win: load_dotenv does not override what is already set, so
docker-compose and Cloud Run keep behaving exactly as they did.
"""

from dotenv import load_dotenv

load_dotenv(override=False)

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ground.routers.passport import router as passport_router
from ground.routers.observations import router as observations_router
from ground.routers.outbreaks import router as outbreaks_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Annadata Setu — Ground Service",
    description="Earth Engine satellite telemetry, SoilGrids, Open-Meteo weather, spatial Firestore queries, and DBSCAN outbreak radar.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(passport_router)
app.include_router(observations_router)
app.include_router(outbreaks_router)

@app.get("/health")
def health():
    from ground.services.geocode import geocode_service

    geocode = geocode_service.status()
    return {
        "status": "ok",
        "service": "as-ground",
        "port": 8003,
        "version": "1.0.0",
        # Unconfigured geocoding is not an outage, but it does mean every plot
        # the caller does not name a district for is labelled Nashik.
        "geocoding": geocode,
    }
