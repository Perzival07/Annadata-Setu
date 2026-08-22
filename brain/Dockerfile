# Build context is the REPO ROOT, not this folder — the shared, frozen
# contracts/ package lives outside the service and must be copied in.
#   docker build -f brain/Dockerfile .
FROM python:3.11-slim
WORKDIR /app

# Requirements before source so the dependency layer survives code edits.
COPY brain/requirements.txt ./brain/requirements.txt
RUN pip install --no-cache-dir -r brain/requirements.txt

COPY contracts/ ./contracts/
# Carries prompts/ and the persisted ChromaDB store in data/chroma/. The ICAR
# source PDFs are excluded by .dockerignore — ingest.py is a one-off you run
# locally, so the image only needs the embeddings it produced.
COPY brain/ ./brain/

# Cloud Run injects PORT and ignores EXPOSE; the default keeps local runs and
# docker-compose on the port BRAIN.md §3 assigns this service.
ENV PORT=8002
EXPOSE 8002

# `brain.main:app`, not `main:app` — imports are absolute from the repo root
# so that `contracts` resolves the same way in the container as it does locally.
CMD ["sh", "-c", "uvicorn brain.main:app --host 0.0.0.0 --port ${PORT}"]
