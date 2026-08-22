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
    return {
        "status": "ok",
        "service": "as-ground",
        "port": 8003,
        "version": "1.0.0"
    }
