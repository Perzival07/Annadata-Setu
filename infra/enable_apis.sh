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
  --project ${PROJECT_ID}

echo "✅ All GCP APIs enabled!"
