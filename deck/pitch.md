# 🌾 Annadata Setu — Pitch Deck

## Slide 1: The Problem
- **Context**: Smallholder farmers in India lose up to 35% of crop yields to disease outbreaks each year.
- **Current reality**: Farmers type long descriptions in apps they don't understand, or wait weeks for extension officers.

## Slide 2: The Solution — WhatsApp-Native Agricultural Nervous System
- One leaf photo + one location pin on WhatsApp.
- Spoken audio diagnosis in regional languages (Marathi) delivered in under 15 seconds.
- No app downloads, no typing required.

## Slide 3: Telemetry & Plot Context
- Beyond the leaf: 3 years of Sentinel-2 satellite NDVI imagery, SoilGrids composition, and 10-day weather forecasts.
- The AI diagnoses the **plot**, not just the visual leaf.

## Slide 4: The "Don't Spray" Path
- Abiotic nutrient deficiencies are distinguished from fungal infections.
- Telling a farmer to save ₹900 by NOT spraying unnecessary chemicals builds ultimate trust.

## Slide 5: The Outbreak Radar & 15km Ring Warnings
- Every diagnosis quietly becomes epidemiological data.
- When 5+ farmers report a disease in a 5km cell, pre-emptive alerts push to every plot in the surrounding 15km ring before infection hits.

## Slide 6: Digital Public Good (DPG) & Open Schemas
- Apache 2.0 licensed open JSON-LD data standards (`plot-passport`, `disease-observation`, `advisory-event`, `model-registry`).
- Any state can fork Maharashtra's model to Karnataka or Punjab overnight.

## Slide 7: Tech Architecture
- **Channel**: WhatsApp Cloud API, Cloud STT Chirp v2, Cloud TTS (`.ogg/opus`).
- **Brain**: Gemini 2.5 Flash schema-locked JSON, ChromaDB RAG over ICAR PDFs.
- **Ground**: Earth Engine Sentinel-2, SoilGrids, Open-Meteo, Firestore Native, DBSCAN clustering.
- All deployed on **GCP Cloud Run in `asia-south1` (Mumbai)**.

## Slide 8: Team & Vision
- Building the open intelligence layer on top of AgriStack.
