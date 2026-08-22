# TODO(P2): FastAPI app, port 8002
from fastapi import FastAPI

app = FastAPI(title="Annadata Setu - Brain Service", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "brain"}
