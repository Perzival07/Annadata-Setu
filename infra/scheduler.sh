#!/usr/bin/env bash
set -euo pipefail

# Deploy the outbreak radar function and its */30 cron trigger.
#
# The function needs CHANNEL_URL and GROUND_URL: without them it falls back to
# localhost, finds nothing, and the sweep silently does nothing every 30 minutes.
# Run infra/deploy.sh first — it prints the exports to paste here.

PROJECT_ID=${GCP_PROJECT_ID:-"annadata-setu"}
REGION=${GCP_REGION:-"asia-south1"}
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${CHANNEL_URL:?Set CHANNEL_URL (printed by infra/deploy.sh)}"
: "${GROUND_URL:?Set GROUND_URL (printed by infra/deploy.sh)}"

echo "☁️  Deploying outbreak_radar function..."
gcloud functions deploy outbreak-radar \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --gen2 \
  --runtime python311 \
  --source "${REPO_ROOT}/functions/outbreak_radar" \
  --entry-point main \
  --trigger-http \
  --no-allow-unauthenticated \
  --set-env-vars "CHANNEL_URL=${CHANNEL_URL},GROUND_URL=${GROUND_URL}"

# Read the URL back rather than guessing it — the Gen2 hostname is not the
# ${REGION}-${PROJECT}.cloudfunctions.net pattern the old script assumed.
FUNCTION_URL=$(gcloud functions describe outbreak-radar \
  --project "${PROJECT_ID}" --region "${REGION}" --gen2 \
  --format='value(serviceConfig.uri)')
SERVICE_ACCOUNT=$(gcloud functions describe outbreak-radar \
  --project "${PROJECT_ID}" --region "${REGION}" --gen2 \
  --format='value(serviceConfig.serviceAccountEmail)')

echo "⏰ Configuring Cloud Scheduler (*/30 * * * *) → ${FUNCTION_URL}"
# create fails if the job already exists; update it instead of erroring out on
# every re-run.
if gcloud scheduler jobs describe outbreak-radar-cron \
     --project "${PROJECT_ID}" --location "${REGION}" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi

gcloud scheduler jobs "${ACTION}" http outbreak-radar-cron \
  --project "${PROJECT_ID}" \
  --location "${REGION}" \
  --schedule="*/30 * * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="${FUNCTION_URL}" \
  --http-method=POST \
  --oidc-service-account-email="${SERVICE_ACCOUNT}" \
  --oidc-token-audience="${FUNCTION_URL}"

echo "✅ Outbreak radar scheduled (*/30 * * * *, Asia/Kolkata)."
