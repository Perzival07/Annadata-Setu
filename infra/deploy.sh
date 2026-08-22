#!/usr/bin/env bash
set -e

PROJECT_ID=${GCP_PROJECT_ID:-"annadata-setu"}
REGION=${GCP_REGION:-"asia-south1"}

echo "🚀 Deploying Annadata Setu Microservices to Cloud Run (${REGION})..."

# 1. Deploy Ground Service (P3)
echo "📦 Deploying as-ground (Port 8003)..."
gcloud run deploy as-ground \
  --source ./ground \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8003 \
  --set-env-vars MOCK_MODE=true

# 2. Deploy Brain Service (P2)
echo "🧠 Deploying as-brain (Port 8002)..."
gcloud run deploy as-brain \
  --source ./brain \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8002 \
  --set-env-vars MOCK_MODE=true

# 3. Deploy Channel Service (P1)
echo "📱 Deploying as-channel (Port 8001)..."
gcloud run deploy as-channel \
  --source ./channel \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8001 \
  --set-env-vars MOCK_MODE=true

echo "✅ All 3 services deployed successfully to Cloud Run in ${REGION}!"
