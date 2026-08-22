import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from channel.routers.webhook import router as webhook_router
from channel.routers.diagnose import router as diagnose_router
from channel.routers.alerts import router as alerts_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Annadata Setu — Channel Service",
    description="WhatsApp Cloud API webhook, STT (Chirp), TTS, response composer, and PWA gateway.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(diagnose_router)
app.include_router(alerts_router)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "as-channel",
        "port": 8001,
        "version": "1.0.0"
    }
