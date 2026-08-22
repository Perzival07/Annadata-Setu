# 🧠 BRAIN.md — Annadata Setu

> **Read this file before writing any code.**
> If your change contradicts this document, the document wins — or you update the document first and tell the team.

**Hackathon:** Build with AI — Code for Communities
**Team:** 3 people · **Time:** 2 days + Day 0 evening
**Region:** `asia-south1` (Mumbai) — everything, no exceptions

---

## 1. What we are building

A **WhatsApp-native agricultural nervous system for India.**

A farmer sends one photo of a sick leaf and one location pin. Nothing else. From that, we pull three years of satellite imagery for their exact plot, soil data, and a 10-day forecast, and return a spoken diagnosis in their own language in under 15 seconds.

Every diagnosis quietly becomes an epidemiological data point. When 5+ farmers in a 5 km cell report the same disease within 7 days, we push a **pre-emptive warning** to every plot in the surrounding 15 km ring — farmers act *before* infection reaches them.

---

## 2. The four sentences that define success

1. The farmer types **nothing** — one pin, one photo.
2. The AI's answer is good because it knows the **plot's context**, not just the leaf.
3. One farmer's question becomes **everyone's early warning**.
4. The schema and API are **open**, so any state can fork it.

If a proposed feature doesn't strengthen one of these four, it does not get built this weekend.

---

## 3. THE ISOLATION RULE — read this twice

This project is built as **three independent services in three separate folders.** Each person owns one folder completely and never opens the other two.

```
P1 → channel/  + web/  + deck/
P2 → brain/    + schema/
P3 → ground/   + functions/ + seed/ + infra/
```

**Nobody edits a file outside their own folder. Ever.**

The only shared code is `contracts/` — three Pydantic models and one HTTP client. It is **frozen after Day 0 evening**. To change anything in it you must announce it in the group chat *before* editing, and both other people must pull immediately.

The three services talk to each other over **HTTP, not imports**. That is the whole point: you can rewrite the inside of your service at 2am and nobody notices, as long as your endpoint still returns the shape defined in `contracts/`.

Each service runs standalone — its own `Dockerfile`, its own `requirements.txt`, its own Cloud Run deployment, its own port.

| Service | Owner | Local port | Cloud Run name |
|---|---|---|---|
| `channel` | P1 | `8001` | `as-channel` |
| `brain` | P2 | `8002` | `as-brain` |
| `ground` | P3 | `8003` | `as-ground` |

---

## 4. Architecture

```
                    WhatsApp Cloud API
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  channel/   (P1)   :8001             │
        │  webhook · STT · TTS · reply         │
        └───────┬──────────────────────┬───────┘
                │ HTTP                 │ HTTP
                ▼                      ▼
   ┌────────────────────┐   ┌────────────────────────┐
   │ ground/  (P3) :8003│◀──│ brain/   (P2)   :8002  │
   │ Earth Engine       │   │ Gemini diagnosis       │
   │ SoilGrids          │   │ RAG over ICAR PDFs     │
   │ Open-Meteo         │   │ rotation engine        │
   │ Firestore + geohash│   │ public API + schema    │
   │ DBSCAN radar       │   └────────────────────────┘
   └────────────────────┘
                │
                ▼
   Cloud Scheduler → functions/outbreak_radar → ring alerts

   web/ (P1): farmer PWA · outbreak heatmap · Looker dashboard
```

### Who calls whom

```
channel  ──POST──▶  ground /plot-passport      (lat,lon → PlotPassport)
channel  ──POST──▶  brain  /diagnose           (image_url + PlotPassport → Diagnosis)
brain    ──POST──▶  ground /observations       (write the diagnosis as a data point)
brain    ──GET───▶  ground /outbreaks/nearby   (context for the prompt)
web      ──GET───▶  brain  /api/v1/outbreaks   (public, GeoJSON, k≥5)
function ──POST──▶  channel /push-alert        (ring alert fan-out)
```

**One direction where possible.** `channel` orchestrates. `ground` never calls `channel` except through the scheduled function.

---

## 5. Repository skeleton

Create this entire tree on Day 0 evening with empty files and `# TODO(P1)` markers. Everyone sees their shape immediately.

```
annadata-setu/
│
├── BRAIN.md                          ← this file. root. everyone reads.
├── README.md                          P2 · public-facing, judges open this
├── .env.example                       P3 · every key listed, no values
├── .gitignore
├── docker-compose.yml                 P3 · runs all 3 services locally
│
├── contracts/                        ⚠️ SHARED — FROZEN after Day 0
│   ├── __init__.py
│   ├── models.py                      the 3 Pydantic models (§6)
│   ├── client.py                      httpx wrapper + MOCK_MODE switch
│   ├── mock_data.py                   hardcoded stub responses
│   └── constants.py                   districts, crop list, thresholds
│
├── channel/                          🟦 P1 ONLY
│   ├── main.py                        FastAPI app, port 8001
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── routers/
│   │   ├── webhook.py                 POST /webhook — Meta inbound
│   │   ├── diagnose.py                POST /api/diagnose — PWA entry point
│   │   └── alerts.py                  POST /push-alert — called by function
│   ├── services/
│   │   ├── whatsapp_in.py             normalise payload, download media→GCS
│   │   ├── whatsapp_out.py            send text / upload+send audio
│   │   ├── stt.py                     Chirp, OGG_OPUS in
│   │   ├── tts.py                     Cloud TTS, OGG_OPUS out
│   │   ├── composer.py                Diagnosis → spoken script
│   │   ├── pipeline.py                the BackgroundTask orchestration
│   │   └── state.py                   new vs returning user, dedupe
│   └── tests/
│       └── smoke.py                   send a fixture payload, assert reply
│
├── brain/                            🟩 P2 ONLY
│   ├── main.py                        FastAPI app, port 8002
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── routers/
│   │   ├── diagnose.py                POST /diagnose → Diagnosis
│   │   ├── rotation.py                POST /rotation → RotationPlan
│   │   └── public_api.py              GET /api/v1/{outbreaks,schema,models}
│   ├── services/
│   │   ├── gemini.py                  schema-locked calls, single entry point
│   │   ├── rag.py                     ChromaDB retrieve
│   │   ├── ingest.py                  one-off: PDFs → chunks → embeddings
│   │   └── registry.py                Model Registry, fork lineage
│   ├── prompts/
│   │   ├── diagnosis.md               versioned. edit here, not in code.
│   │   ├── rotation.md
│   │   └── reply_marathi.md
│   ├── data/
│   │   ├── icar_pdfs/                 ~30 Package-of-Practices PDFs
│   │   └── chroma/                    persisted vector store (committed)
│   └── tests/
│       └── eval_photos.py             15 photos → expected labels
│
├── ground/                           🟨 P3 ONLY
│   ├── main.py                        FastAPI app, port 8003
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── routers/
│   │   ├── passport.py                POST /plot-passport → PlotPassport
│   │   ├── observations.py            POST /observations, GET /nearby
│   │   └── outbreaks.py               GET /outbreaks → list[Outbreak]
│   ├── services/
│   │   ├── earth_engine.py            Sentinel-2 NDVI/NDWI 3yr + fallback
│   │   ├── soil.py                    SoilGrids + district-average fallback
│   │   ├── weather.py                 Open-Meteo, 4-night RH average
│   │   ├── crop_infer.py              NDVI curve → crop, stage, history
│   │   ├── passport.py                asyncio.gather aggregator + cache
│   │   ├── firestore.py               ALL db access lives here, nowhere else
│   │   ├── geo.py                     geohash encode, prefix range, adjacency
│   │   └── cluster.py                 DBSCAN, k-anonymity, ring lookup
│   └── tests/
│       └── test_cluster.py            seed data must yield exactly 1 hotspot
│
├── functions/                        🟨 P3
│   └── outbreak_radar/
│       ├── main.py                    Cloud Function Gen2, */30 cron
│       └── requirements.txt
│
├── seed/                             🟨 P3
│   ├── generate.py                    writes 60 designed observations
│   ├── observations.json
│   ├── plots.json                     42 silent plots in the alert ring
│   └── ndvi_fallback/
│       ├── nashik.json                pre-exported — EE outage insurance
│       └── vidarbha.json
│
├── web/                              🟦 P1
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx                    router: /farmer /map /about
│       ├── api.js                     one place for all base URLs
│       ├── pages/
│       │   ├── Farmer.jsx             PWA fallback: capture → geo → result
│       │   ├── OutbreakMap.jsx        HeatmapLayer over /api/v1/outbreaks
│       │   └── Dashboard.jsx          embedded Looker Studio iframe
│       └── components/
│           ├── CaptureCard.jsx
│           ├── DiagnosisCard.jsx
│           └── AlertRing.jsx
│
├── schema/                           🟩 P2 · THE DPG ARTIFACT
│   ├── LICENSE                        Apache 2.0
│   ├── README.md                      how another state adopts this
│   ├── plot-passport.v1.jsonld
│   ├── disease-observation.v1.jsonld
│   ├── advisory-event.v1.jsonld
│   ├── model-registry.v1.jsonld
│   └── sample-dataset.json
│
├── infra/                            🟨 P3
│   ├── deploy.sh                      3 × gcloud run deploy
│   ├── enable_apis.sh
│   └── scheduler.sh
│
└── deck/                             🟦 P1
    ├── pitch.md                       8 slides, narrative first
    ├── demo_script.md                 §13, memorised
    └── backup_demo.mp4                recorded Day 2 morning
```

---

## 6. `contracts/models.py` — FROZEN

The interface between all three services. Announce before changing. Stubs returning hardcoded values must exist from **Day 0 evening** so nobody blocks on anyone.

```python
class PlotPassport(BaseModel):
    plot_id: str                    # deterministic hash of geohash
    lat: float
    lon: float
    geohash: str                    # 7 chars — this is our spatial index
    district: str
    state: str
    ndvi_series: list[dict]         # [{"date": "2024-03-01", "value": 0.62}]
    inferred_crop: str
    crop_stage_days: int
    cropping_history: list[str]     # ["tomato", "tomato", "onion"]
    soil: dict                      # {"ph": 6.4, "soc": 0.51, "texture": "loam"}
    weather_10d: dict               # {"rh_avg": 87, "rain_mm": 42, "temp_max": 31}
    data_sources: list[str]         # provenance — needed for the DPG claim
    schema_version: str = "1.0"


class Diagnosis(BaseModel):
    disease_name: str
    confidence: float               # 0.0–1.0
    differentials: list[str]
    is_action_needed: bool          # False → the "don't spray" path
    action_text: str
    dosage: str | None
    estimated_cost_inr: int
    urgency_hours: int
    escalate_to_human: bool         # True when confidence < 0.65
    reasoning_context: list[str]    # ["RH >85% for 4 nights", "day 58 tomato"]
    sources: list[str]              # ICAR filenames used by RAG


class Outbreak(BaseModel):
    cluster_id: str
    disease: str
    centroid: tuple[float, float]
    radius_km: float
    report_count: int               # NEVER serialised if < 5
    distinct_plots: int             # must be >= 3
    first_seen: datetime
    alert_ring_km: float = 15.0
```

### `contracts/client.py` — the unblocking mechanism

```python
MOCK = os.getenv("MOCK_MODE", "false") == "true"

async def get_plot_passport(lat, lon) -> PlotPassport:
    if MOCK:
        return mock_data.PASSPORT          # ← P1 works before P3 ships
    return PlotPassport(**await post(GROUND_URL + "/plot-passport", ...))
```

**Every service runs with `MOCK_MODE=true` until its dependency is live.** This is why three people can build in parallel from hour one.

---

## 7. Non-negotiables

| Rule | Why |
|---|---|
| Never edit outside your folder | Merge conflicts at 2am kill hackathon teams |
| Every Gemini call uses a **strict response schema** | Free-text parsing will break the live demo |
| Webhook returns **HTTP 200 within 3s**, work in `BackgroundTask` | WhatsApp retries on timeout → duplicate replies |
| Clusters with **< 5 reports never returned** — enforced in the query | k-anonymity. A pitch point. Not a UI filter. |
| Every external API call has a **hardcoded fallback** | EE quota, Meta limits, and demo wifi are all real |
| One GCP project, one `.env`, region `asia-south1` | Cross-region latency on stage is unforced error |
| No PII beyond phone number — data is about the **plot** | Sidesteps the privacy problem entirely |
| The **"don't spray"** path must work | Telling a farmer to save ₹900 is our trust story |

---

## 8. Tech stack — decided, not up for debate

**Backend:** Python 3.11 · FastAPI · Cloud Run (3 services)
**AI:** Gemini 2.5 Flash via `google-genai` (AI Studio key, *not* Vertex)
**RAG:** ChromaDB in-process, persisted into the image · `text-embedding-004`
**Satellite:** Earth Engine Python API — Sentinel-2 SR Harmonized
**Soil:** ISRIC SoilGrids REST · **Weather:** Open-Meteo (no key)
**DB:** Firestore Native — **geohash prefix ranges, no native radius search**
**Voice:** Cloud STT (Chirp) in · Cloud TTS out, **OGG_OPUS**
**Frontend:** React 18 + Vite + Tailwind · Firebase Hosting
**Maps:** `@vis.gl/react-google-maps` HeatmapLayer
**Clustering:** `scikit-learn` DBSCAN · `pygeohash`
**Dashboard:** BigQuery → Looker Studio

Pin `google-genai`. The old `google-generativeai` is deprecated — **do not import it.**

---

## 9. Conventions

- **Fallbacks are mandatory.** Every external call wrapped:
  ```python
  try:
      return await real_call()
  except Exception as e:
      log.warning(f"{source} failed, using fallback: {e}")
      return FALLBACK[district]
  ```
- **Log every stage with `plot_id`.** When the demo misbehaves you have 90 seconds to find out why.
- **Structured output only.** No regex over LLM prose. Ever.
- **`snake_case`** in Python and all JSON, including the public API.
- Branch per person: `p1/channel`, `p2/brain`, `p3/ground`. Merge to `main` at 13:00 and 23:00 Day 1, 12:00 Day 2.
- Commits prefixed: `[P1] fix audio mimetype for whatsapp`
- Secrets in `.env`, never committed. **P3 owns the canonical `.env`** and shares it once.

---

## 10. Day 0 evening — 3 to 4 hours, not optional

| | P1 | P2 | P3 |
|---|---|---|---|
| **First 45 min** | Meta dev account, WhatsApp sandbox, ngrok, **echo a message** | AI Studio key, one Gemini multimodal call with schema output | **Apply for Earth Engine access — before anything else.** Then GCP project, enable APIs |
| **Next 45 min** | Scaffold `channel/`, FastAPI up on 8001 | Write `contracts/models.py` + `mock_data.py`, **commit** | Firestore Native, Firebase linked, write `.env`, share it |
| **Next hour** | Verify `.ogg` round-trip to your own phone | Write `contracts/client.py` with `MOCK_MODE` | Pre-export NDVI JSON for 2 districts → `seed/ndvi_fallback/` |
| **Last hour** | Together: create the **entire tree from §5** with empty files. Pick **the crop and district.** Collect 15 leaf photos. Download 30 ICAR PDFs. |

**Gate:** nobody sleeps until `contracts/` is on `main` and everyone has pulled. From that moment, nobody is blocked by anyone.

---

## 11. Day 1 — three parallel tracks

**Shared gates: 13:00 mock→real swap · 18:00 END-TO-END · 23:00 merge**

### 🟦 P1 — `channel/` + `web/`

| Time | Build |
|---|---|
| 09:15 | `whatsapp_in.py` — normalise payload. 4 types: text, image, audio, location. Ignore `status` callbacks. Media is a **two-step fetch** — `media_id` → URL → fetch *with bearer token*. |
| 10:30 | `pipeline.py` — return 200 in <3s, run in `BackgroundTask`, dedupe on Meta's `message_id` **in Firestore** (Cloud Run scales to zero). Send an instant ack: *"Got it, checking your field 🌱"* |
| 11:45 | `stt.py` — Chirp, `encoding=OGG_OPUS`, `sample_rate=16000` explicitly, or you get silent empty transcripts |
| **13:00** | **Flip `MOCK_MODE=false`.** Real calls to `ground` and `brain`. |
| 14:00 | `tts.py` — **the trap.** OGG_OPUS only. Upload to Meta `/media` first → get ID → send *that*. Set `mimeType: "audio/ogg; codecs=opus"`. Do a hardcoded "hello" round-trip **before** wiring real diagnosis. |
| 15:30 | `composer.py` — *what it is → why you're getting it → what to do → what it costs.* Send voice **and** text. Ask Gemini for Marathi directly, don't translate. Listen to it yourself. |
| **17:00** | 🎯 **END TO END on a real phone.** Not working by 18:00 → say so loudly, all three swarm. |
| 19:00 | `web/pages/Farmer.jsx` — PWA fallback, 90 min. Insurance against Meta rate-limiting you on stage. |
| 20:30 | `state.py` — new vs returning user. Feedback 👍/👎 → `POST ground/observations`. |
| 22:30 | `deck/pitch.md` — 8 slides, structure only. |

### 🟩 P2 — `brain/`

| Time | Build |
|---|---|
| 09:15 | `gemini.py` — `response_mime_type="application/json"`, `response_schema=Diagnosis`, `temperature=0.2`. **Test 10 calls on one photo; all 10 must parse.** |
| 10:30 | `prompts/diagnosis.md` — inject the full plot context. Populate `reasoning_context` with facts actually used — that field is demo gold. Iterate on the 15 photos. |
| 12:00 | Confidence calibration on blurry/dark/wrong-crop shots. `<0.65 → escalate_to_human`. Always fill `differentials[]`. |
| **13:00** | **Flip `MOCK_MODE=false`.** Real `PlotPassport` from P3. **Confirm the diagnosis changes when context changes.** |
| 14:00 | `ingest.py` → `rag.py`. Semantic chunks ~800 tokens, `text-embedding-004`, ChromaDB `PersistentClient`. Top-4 on `{crop} {disease} management`. Prompt rule: *if retrieved docs don't specify a dosage, say so — never invent one.* Keep filenames in `sources[]`. |
| 16:00 | The **"don't spray"** path. Force abiotic consideration explicitly. Find a nutrient-deficiency photo and **verify it fires.** Screenshot RAG-off vs RAG-on — that's a slide. |
| 17:00 | Support P1's end-to-end push. Keep this hour free. |
| 19:00 | `rotation.py` — quantified output: `n_fixed_kg_ha`, `water_saved_litres`, `income_delta_inr`, `residue_advice`, `peer_proof`. **Peer proof beats AI authority** in Indian agriculture. |
| 21:00 | `public_api.py` + `schema/`. Clean `/docs` — **this auto-generated page is half your DPG evidence.** Push `schema/` **public tonight** — a live GitHub URL in the deck beats a promise. Model Registry: 3 entries with fork lineage (MH tomato v1.2 → KA v1.2.1). |

### 🟨 P3 — `ground/` + `seed/` + `functions/`

| Time | Build |
|---|---|
| 09:00 | **Check EE approval.** Not approved → build fallback-first, recheck at 14:00 and 18:00. **Do not sit and wait.** |
| 09:15 | `earth_engine.py` — 150m buffer (~7ha). **Cloud masking is not optional** in monsoon India. `getInfo()` blocks 4–8s — never in the request path. Every call in try/except → seed JSON. |
| 11:00 | `soil.py` (SoilGrids values are ×10 — divide) + `weather.py` (4-night RH average = the disease-pressure signal P2 needs). |
| 12:00 | `firestore.py` + `geo.py`. **Geohash, not GeoPoint.** 7 chars on write; precision-5 prefix ≈ 5km cell. Include the 8 adjacent cells so boundary-straddling clusters aren't missed. |
| **13:00** | **Ship the real `/plot-passport` endpoint.** Tell P1 and P2 to flip `MOCK_MODE`. |
| 14:00 | `passport.py` — `asyncio.gather` the three fetches with `return_exceptions=True`. **Cache by geohash, 7-day TTL.** Second demo run drops 12s → 2s, and that's noticeable on stage. Fill `data_sources[]`. |
| 16:00 | `crop_infer.py` — **the "she typed nothing" magic.** `find_peaks` on the NDVI series → seasons, kharif/rabi, stage days, monoculture flag. A heuristic table for your district's 4–5 crops is enough. **Sanity-check against known ground truth for the demo location.** |
| 19:00 | `seed/generate.py` — **design it, don't randomise.** 1 hotspot (7 reports, one 5km cell, 6 days, growing) · 2 sub-threshold clusters of 3 (these must *not* appear — proves k-anonymity) · 40 scattered · **42 silent plots in the 15km ring** (that number is your demo punchline). |
| 21:00 | `cluster.py` — DBSCAN haversine, `eps=5/6371`, `min_samples=5`, 7-day window, **grouped by disease**. `if len(cluster) < 5: continue` **and** `distinct_plots >= 3`. Build as a plain function, test on seed data, **only then** wire Cloud Scheduler. |

---

## 12. Day 2

**08:00–12:00** — P1: `OutbreakMap.jsx` heatmap · P2: public API polish + Model Registry + README · P3: **ring alert fan-out** — cluster forms → geohash ring query → `POST channel/push-alert`

**🔒 12:00 — FEATURE FREEZE.** No new code paths. Every team that ignores this loses.

**12:30–15:00** — All three together. Full demo path **3× back to back**, cold start included. Fix only what breaks the demo. P1 builds the Looker dashboard (40 min, drag-and-drop, highest value-per-minute artifact in the build). Verify "don't spray" fires. Verify escalation fires on a blurry photo.

**15:00–16:30** — P1: **record the 90-second backup video** — non-negotiable, demo wifi has ended more runs than bad code. P2: README + architecture diagram. P3: cache demo diagnoses by image hash, pre-warm the passport cache.

**16:30–18:00** — **Five full rehearsals, out loud, timed.** Then hostile Q&A between yourselves: *How is this different from Plantix? Farmers without smartphones? Is the AI accurate enough to give dosages? What stops this becoming surveillance? Have you talked to a farmer?*

---

## 13. Demo script — memorise the beats

> Meera farms 1.2 acres of tomato in Nashik. She opens WhatsApp — no app to install — sends a leaf photo and her location.
>
> *[8 seconds]* Voice note in Marathi: *"Early blight. Your plot is day 58. Rain Thursday will spread it. Spray mancozeb 2g per litre tomorrow morning — about ₹340. Nearest supplier is 3 km away."*
>
> What Meera never saw: three years of Sentinel-2 for her plot, four straight seasons of tomato, soil carbon, humidity forecast — all from one pin.
>
> Now watch. *[map]* Her report is the fifth in this 5 km cell. Forty-two farmers who reported **nothing** just got warned. They'll act before they see a spot on a leaf.
>
> *[dashboard]* The district officer sees this outbreak today, not in next month's report. Schema, API and models are open — Karnataka forks Maharashtra's tomato model tomorrow.

**Q&A positioning:** *Plantix does image ID. AgriStack builds identity rails. Nobody does farmer-sourced disease surveillance with pre-emptive neighbour alerts. We're the advisory layer on top of AgriStack — complementary, not competing.*

---

## 14. Known traps

| Trap | Mitigation |
|---|---|
| **EE registration takes hours–days** | Apply Day 0 first thing. Seed fallback regardless. |
| WhatsApp retries slow webhooks → duplicate replies | 200 immediately + dedupe on `message_id` |
| WhatsApp audio must be OGG/opus, uploaded to `/media` first | Hardcoded round-trip test before wiring real output |
| Firestore has no radius query | Geohash prefix ranges — already decided, don't rediscover |
| Gemini free-tier rate limits | Cache by image hash during rehearsal |
| Vertex Vector Search takes 45+ min per deploy | We use ChromaDB. Say "Vertex in production" in the pitch. |
| Demo wifi | The 90-second backup video. Non-negotiable. |

---

## 15. Explicitly out of scope

❌ Custom CNN ❌ Auth/login ❌ Kubernetes, Terraform, CI/CD ❌ PostGIS or any SQL DB ❌ React Native/Flutter ❌ Real IMD API ❌ Actual federated learning *(roadmap slide only)* ❌ Redis/Celery/queues ❌ Marketplace, payments, mandi prices ❌ Multi-crop — **one crop, one district, deep**

**If behind at 18:00 Day 1, sacrifice in this order:** rotation engine → PWA → BigQuery → feedback loop. **Never** the outbreak radar — that's the differentiator no other team will have.

---

## 16. If you're an AI assistant reading this

- You are working inside **one folder only**. Identify which from the user's context and **do not create or edit files outside it.**
- `contracts/models.py` is frozen. Never invent, rename, or drop a field. If a task seems to require a contract change, **stop and flag it.**
- Never remove a fallback (§9). Never emit unstructured LLM output where a schema is specified (§7).
- Services communicate over **HTTP via `contracts/client.py`**, never by importing each other's modules.
- When §15 conflicts with a request, flag the conflict before building.
