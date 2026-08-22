import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from brain.routers.diagnose import router as diagnose_router
from brain.routers.rotation import router as rotation_router
from brain.routers.public_api import router as public_api_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Annadata Setu — Brain Service",
    description="Gemini 2.5 Flash diagnosis, ICAR PDF RAG, crop rotation advisor, and public DPG schemas.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(diagnose_router)
app.include_router(rotation_router)
app.include_router(public_api_router)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "as-brain",
        "port": 8002,
        "version": "1.0.0"
    }
