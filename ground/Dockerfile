# Build context is the REPO ROOT, not this folder — the shared, frozen
# contracts/ package lives outside the service and must be copied in.
#   docker build -f ground/Dockerfile .
FROM python:3.11-slim
WORKDIR /app

# Requirements before source so the dependency layer survives code edits.
COPY ground/requirements.txt ./ground/requirements.txt
RUN pip install --no-cache-dir -r ground/requirements.txt

COPY contracts/ ./contracts/
COPY ground/ ./ground/
# NDVI fallbacks and the seeded observations — the Earth Engine outage
# insurance travels with the image (BRAIN.md §14).
COPY seed/ ./seed/

# Cloud Run injects PORT and ignores EXPOSE; the default keeps local runs and
# docker-compose on the port BRAIN.md §3 assigns this service.
ENV PORT=8003
EXPOSE 8003

# `ground.main:app`, not `main:app` — imports are absolute from the repo root
# so that `contracts` resolves the same way in the container as it does locally.
CMD ["sh", "-c", "uvicorn ground.main:app --host 0.0.0.0 --port ${PORT}"]
