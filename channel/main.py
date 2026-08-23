"""Channel service entrypoint (P1).

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
    from channel.services.translate import translate_service
    from channel.services.media import media_archive_service

    return {
        "status": "ok",
        "service": "as-channel",
        "port": 8001,
        "version": "1.0.0",
        "translation": translate_service.status(),
        # Worth seeing at a glance: with the archive off, every escalation tells
        # a farmer an expert will review a photo that is not being kept.
        "media_archive": media_archive_service.status(),
    }
