# 🌾 Annadata Setu (🌱 अन्नदाता सेतु)

A WhatsApp-native agricultural nervous system for India.

## Overview
- **Channel (`channel/` - P1):** WhatsApp Cloud API webhook, STT (Chirp), TTS, response composer, Cloud Translate on the fallback voice script, Cloud Storage archive for escalated photos.
- **Brain (`brain/` - P2):** Gemini diagnosis with Google Search grounding and function calling, RAG over ICAR PDFs, crop rotation advisor, public API & DPG schemas.
- **Ground (`ground/` - P3):** Earth Engine satellite telemetry, Maps reverse geocoding, SoilGrids, Open-Meteo weather, Firestore spatial queries, DBSCAN outbreak radar.

See [`BRAIN.md`](./BRAIN.md) for full architecture and specifications.

## Running it

Three FastAPI services plus a Vite frontend. Every command runs **from the repo
root** — imports are absolute (`brain.main:app`, not `main:app`) so that the
shared `contracts/` package resolves the same way locally as in the container,
and `seed/observations.json` is read by relative path.

### Docker (one command)

```bash
docker compose up --build
```

Brings up all three services on 8001/8002/8003 with `MOCK_MODE=true` and a local
datastore primed from `seed/`. Reads `.env` if present; it is optional.

### Local (no Docker)

```bash
python -m venv .venv
.venv/bin/pip install -r brain/requirements.txt \
                      -r channel/requirements.txt \
                      -r ground/requirements.txt

export MOCK_MODE=true FORCE_LOCAL_DB=true

.venv/bin/uvicorn ground.main:app  --port 8003 &   # start first — the others call it
.venv/bin/uvicorn brain.main:app   --port 8002 &
.venv/bin/uvicorn channel.main:app --port 8001 &

cd web && npm install && npm run dev              # http://localhost:3000
```

Start `ground` first: `brain` writes observations to it and `channel` fetches
plot context through it.

### Check it came up

```bash
curl localhost:8001/health   # channel — translation + media archive status
curl localhost:8002/health   # brain   — RAG corpus size + gemini tool status
curl localhost:8003/health   # ground  — geocoding status
```

`brain` reports `"status": "degraded"` when the RAG corpus is empty — retrieval
still answers, but from built-in notes with nothing citable behind them. A
healthy corpus reports `indexed_chunks` in the hundreds.

### Drive the demo path

```bash
# One farmer: photo + pin -> diagnosis, WhatsApp text, spoken Marathi script
curl -X POST localhost:8001/api/diagnose -H 'Content-Type: application/json' \
  -d '{"image_base64":"<base64 jpeg>","lat":19.9975,"lon":73.7898}'

# The epidemiological layer: clusters at or above the k-anonymity threshold
curl localhost:8003/outbreaks
curl 'localhost:8003/alert-ring?lat=19.9975&lon=73.7898&radius_km=15'   # -> 42 plots

# The public DPG feed (GeoJSON)
curl localhost:8002/api/v1/outbreaks

# The scheduled sweep that sends pre-emptive alerts to the ring
CHANNEL_URL=http://localhost:8001 GROUND_URL=http://localhost:8003 \
  .venv/bin/python functions/outbreak_radar/main.py
```

### Modes

`MOCK_MODE=true` is the credential-free demo: `brain` returns the fixture
diagnosis, STT/TTS return stub bytes, Earth Engine and Firestore stay local.

`MOCK_MODE=false` is the real path. Without `GEMINI_API_KEY` it does not guess —
every diagnosis comes back `escalate_to_human` with no dosage and no cost. Set
`FORCE_LOCAL_DB=true` to keep the datastore in-process when you have no GCP
credentials.

### Rebuilding the corpus

The ChromaDB store is committed, so this is only needed after changing the PDFs:

```bash
.venv/bin/python -m brain.services.ingest --reset   # reads brain/data/icar_pdfs/
.venv/bin/python -m seed.generate                   # regenerate the seed dataset
```

### Tests

```bash
.venv/bin/python -m unittest brain.tests.test_schema brain.tests.test_rag \
  brain.tests.test_tools channel.tests.smoke channel.tests.test_marathi \
  channel.tests.test_google_services channel.tests.test_languages \
  ground.tests.test_cluster ground.tests.test_geocode
```

## Gemini tool use

A diagnosis runs in two phases, because the Gemini API will not accept `tools`
and a `response_schema` on the same request:

| Phase | Tools | Schema | What it does |
|---|---|---|---|
| Gather (`brain/services/grounding.py`) | Google Search + our own services as functions | none | The model issues its own ICAR queries, checks nearby outbreaks, and searches for current district advisories |
| Decide (`brain/services/gemini.py`) | none | `Diagnosis` | Produces the structured advisory, with the gather notes as context |

The gather phase is **off by default** (`ENABLE_GEMINI_TOOLS=true` turns it on),
time-boxed, and fails soft — an empty gather leaves the diagnosis exactly as it
was before tools existed.

Two rules hold regardless:

- **A dosage comes only from a retrieved ICAR document.** A web page is
  corroborating context, never a prescription source. This is enforced in the
  gather prompt, the diagnosis prompt, and conformance rule 5 of the DPG schema.
- **Citations come from `grounding_metadata`,** the URLs Google reports having
  fetched — never from URLs the model wrote in its output. They land in
  `Diagnosis.web_sources`, kept separate from the reviewed `sources`.

## Optional services

Each is off unless configured, and each degrades to the behaviour that preceded it:

| Setting | Off means |
|---|---|
| `ENABLE_GEMINI_TOOLS` | Diagnosis runs on pre-fetched context only |
| `GOOGLE_MAPS_API_KEY` | A plot whose caller names no district is labelled Nashik |
| `ENABLE_TRANSLATION` | The fallback voice script drops `action_text` rather than speaking it |
| `MEDIA_ARCHIVE_BUCKET` | Escalated photos are not retained for the review we promise |

`/health` on each service reports which of these are actually live.
