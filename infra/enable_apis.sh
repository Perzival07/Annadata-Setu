#!/usr/bin/env bash
set -e

PROJECT_ID=${GCP_PROJECT_ID:-"annadata-setu"}

echo "🔧 Enabling GCP APIs for Annadata Setu in project ${PROJECT_ID}..."

gcloud services enable \
  run.googleapis.com \
  earthengine.googleapis.com \
  firestore.googleapis.com \
  speech.googleapis.com \
  texttospeech.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  geocoding-backend.googleapis.com \
  translate.googleapis.com \
  storage.googleapis.com \
  --project ${PROJECT_ID}

echo "✅ All GCP APIs enabled!"
echo
echo "Note: enabling geocoding-backend does not create a key. GOOGLE_MAPS_API_KEY"
echo "must be an API key from the Credentials page, restricted to the Geocoding API."
echo "Gemini search grounding needs no separate API — it is billed through"
echo "GEMINI_API_KEY as part of generateContent."
