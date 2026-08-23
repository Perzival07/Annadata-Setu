"""Brain service entrypoint (P2).

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
    # The RAG corpus is reported here because an empty one is otherwise
    # invisible: retrieval keeps answering, just with nothing citable behind it.
    from brain.services.rag import rag_service
    from brain.services import grounding
    from brain.services.genai_pool import gemini_pool

    rag = rag_service.status()
    return {
        "status": "ok" if rag["sources_citable"] else "degraded",
        "service": "as-brain",
        "port": 8002,
        "version": "1.0.0",
        "rag": rag,
        # Tool use is optional and fails soft, so its absence is silent by
        # design. Report it here or nobody can tell whether the grounded
        # diagnosis they think they configured is actually running.
        "gemini_tools": grounding.status(),
        # How many keys are loaded and which one is currently in use. Only the
        # last four characters of each, never a usable secret.
        "gemini_keys": gemini_pool.status(),
    }
