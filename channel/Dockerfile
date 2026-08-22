# Build context is the REPO ROOT, not this folder — the shared, frozen
# contracts/ package lives outside the service and must be copied in.
#   docker build -f channel/Dockerfile .
FROM python:3.11-slim
WORKDIR /app

# Requirements before source so the dependency layer survives code edits.
COPY channel/requirements.txt ./channel/requirements.txt
RUN pip install --no-cache-dir -r channel/requirements.txt

COPY contracts/ ./contracts/
COPY channel/ ./channel/

# Cloud Run injects PORT and ignores EXPOSE; the default keeps local runs and
# docker-compose on the port BRAIN.md §3 assigns this service.
ENV PORT=8001
EXPOSE 8001

# `channel.main:app`, not `main:app` — imports are absolute from the repo root
# so that `contracts` resolves the same way in the container as it does locally.
CMD ["sh", "-c", "uvicorn channel.main:app --host 0.0.0.0 --port ${PORT}"]
