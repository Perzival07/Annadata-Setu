# TODO(P1): FastAPI app, port 8001
from fastapi import FastAPI

app = FastAPI(title="Annadata Setu - Channel Service", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "channel"}
