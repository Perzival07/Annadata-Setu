#!/usr/bin/env bash
set -euo pipefail

# Deploy the three services to Cloud Run, in dependency order, wiring each one's
# URL into the services that call it.
#
# Two things this script must get right, because getting them wrong is silent:
#
#  1. BUILD CONTEXT is the repo root. Every Dockerfile does `COPY contracts/`,
#     and contracts/ lives outside the service folders. `gcloud run deploy
#     --source ./ground` scopes the context to that folder, so the COPY fails.
#     We build from the root with an explicit -f instead.
#
#  2. MOCK_MODE stays FALSE. Deploying with MOCK_MODE=true ships a service that
#     answers every farmer with the demo fixture — a confident instruction to
#     spray ₹340 of Mancozeb, generated without looking at anything.

PROJECT_ID=${GCP_PROJECT_ID:-"annadata-setu"}
REGION=${GCP_REGION:-"asia-south1"}
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Override to true only for a deliberate dry run against no live dependencies.
MOCK_MODE=${MOCK_MODE:-false}

if [[ "${MOCK_MODE}" == "true" ]]; then
  echo "⚠️  MOCK_MODE=true — these services will answer with the demo fixture."
  read -r -p "    Deploy anyway? [y/N] " confirm
  [[ "${confirm}" == "y" || "${confirm}" == "Y" ]] || { echo "Aborted."; exit 1; }
fi

if [[ "${MOCK_MODE}" != "true" && -z "${GEMINI_API_KEY:-}" ]]; then
  echo "❌ GEMINI_API_KEY is not set. Without it as-brain escalates every"
  echo "   diagnosis to a human instead of answering. Export it and retry."
  exit 1
fi

# Not fatal, but the operator should know what they are shipping without.
if [[ "${MOCK_MODE}" != "true" && -z "${MEDIA_ARCHIVE_BUCKET:-}" ]]; then
  echo "⚠️  MEDIA_ARCHIVE_BUCKET is not set. Every escalated advisory tells the"
  echo "   farmer an agronomist will review their photo, and nothing will keep"
  echo "   the photo — Meta's media URLs expire."
fi

if [[ "${MOCK_MODE}" != "true" && -z "${GOOGLE_MAPS_API_KEY:-}" && "${GEOCODER:-}" != "none" ]]; then
  echo "ℹ️  GOOGLE_MAPS_API_KEY is not set — reverse geocoding will use"
  echo "   OpenStreetMap Nominatim, which is free but rate limited to ~1 req/s."
  echo "   Fine for a demo; set a Maps key for production traffic."
fi

echo "🚀 Deploying Annadata Setu to Cloud Run (${PROJECT_ID} / ${REGION})..."
echo "   MOCK_MODE=${MOCK_MODE}"

build_and_deploy() {
  local service_dir=$1 service_name=$2 port=$3
  shift 3
  local image="gcr.io/${PROJECT_ID}/${service_name}:$(date +%Y%m%d-%H%M%S)"

  echo "📦 Building ${service_name} from the repo root..."
  # --tag and --config are mutually exclusive, and --tag gives no way to pick a
  # Dockerfile, so the build config is written out explicitly.
  local cfg
  cfg=$(mktemp -t annadata-build-XXXXXX.yaml)
  cat > "${cfg}" <<YAML
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', '${service_dir}/Dockerfile', '-t', '${image}', '.']
images: ['${image}']
YAML
  ( cd "${REPO_ROOT}" && gcloud builds submit --project "${PROJECT_ID}" --config "${cfg}" . )
  rm -f "${cfg}"

  echo "🚢 Deploying ${service_name}..."
  gcloud run deploy "${service_name}" \
    --project "${PROJECT_ID}" \
    --image "${image}" \
    --region "${REGION}" \
    --allow-unauthenticated \
    --port "${port}" \
    "$@"
}

service_url() {
  gcloud run services describe "$1" \
    --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)'
}

# 1. ground — the leaf service, calls nobody.
build_and_deploy ground as-ground 8003 \
  --set-env-vars "MOCK_MODE=${MOCK_MODE},GCP_PROJECT_ID=${PROJECT_ID},GOOGLE_MAPS_API_KEY=${GOOGLE_MAPS_API_KEY:-},GEOCODER=${GEOCODER:-},NOMINATIM_USER_AGENT=${NOMINATIM_USER_AGENT:-}"
GROUND_URL=$(service_url as-ground)
echo "   as-ground  → ${GROUND_URL}"

# 2. brain — writes observations back to ground.
build_and_deploy brain as-brain 8002 \
  --set-env-vars "MOCK_MODE=${MOCK_MODE},GROUND_URL=${GROUND_URL},GEMINI_API_KEY=${GEMINI_API_KEY:-},ENABLE_GEMINI_TOOLS=${ENABLE_GEMINI_TOOLS:-false},GEMINI_TOOLS_BUDGET_S=${GEMINI_TOOLS_BUDGET_S:-20}"
BRAIN_URL=$(service_url as-brain)
echo "   as-brain   → ${BRAIN_URL}"

# 3. channel — orchestrates, so it needs both. GCP_PROJECT_ID is required here
# too: Cloud Translate is addressed as projects/<id>/locations/global.
build_and_deploy channel as-channel 8001 \
  --set-env-vars "MOCK_MODE=${MOCK_MODE},GCP_PROJECT_ID=${PROJECT_ID},GROUND_URL=${GROUND_URL},BRAIN_URL=${BRAIN_URL},WHATSAPP_TOKEN=${WHATSAPP_TOKEN:-},WHATSAPP_PHONE_NUMBER_ID=${WHATSAPP_PHONE_NUMBER_ID:-},META_VERIFY_TOKEN=${META_VERIFY_TOKEN:-},ENABLE_TRANSLATION=${ENABLE_TRANSLATION:-false},MEDIA_ARCHIVE_BUCKET=${MEDIA_ARCHIVE_BUCKET:-},MEDIA_HASH_SALT=${MEDIA_HASH_SALT:-}"
CHANNEL_URL=$(service_url as-channel)
echo "   as-channel → ${CHANNEL_URL}"

echo
echo "✅ Deployed to ${REGION}."
echo "   Meta webhook URL: ${CHANNEL_URL}/webhook"
echo "   Public DPG API:   ${BRAIN_URL}/api/v1/outbreaks"
echo
echo "   Export these before running infra/scheduler.sh:"
echo "     export CHANNEL_URL=${CHANNEL_URL}"
echo "     export GROUND_URL=${GROUND_URL}"
