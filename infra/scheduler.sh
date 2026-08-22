#!/usr/bin/env bash
set -e

REGION=${GCP_REGION:-"asia-south1"}

echo "⏰ Configuring Cloud Scheduler for Outbreak Radar worker..."

gcloud scheduler jobs create http outbreak-radar-cron \
  --schedule="*/30 * * * *" \
  --uri="https://${REGION}-annadata-setu.cloudfunctions.net/outbreak_radar" \
  --http-method=POST \
  --location=${REGION}

echo "✅ Cloud Scheduler job created (cron: */30 * * * *)"
