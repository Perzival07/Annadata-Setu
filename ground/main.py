# TODO(P3): FastAPI app, port 8003
from fastapi import FastAPI

app = FastAPI(title="Annadata Setu - Ground Service", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "ground"}
