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

## Languages

Farmer-facing output is available in **Marathi, Hindi, Bengali and English**.

| | Script | Digits | Voice |
|---|---|---|---|
| `mr` मराठी | Devanagari | `३४०` | `mr-IN` |
| `hi` हिन्दी | Devanagari | `३४०` | `hi-IN` |
| `bn` বাংলা | Bengali | `৩৪০` | `bn-IN` |
| `en` English | Latin | `340` | `en-IN` |

**How a farmer's language is chosen** — four layers, strongest evidence first,
each degrading to the next rather than to a guess:

1. **They chose it.** Texting `hindi`, `3`, `বাংলা` or `language` (for the menu)
   sets it permanently. A decision, so nothing below overrides it.
2. **Their own message.** Cloud Speech reports which language a voice note was
   in; a text message is read by script. Devanagari is ambiguous between Hindi
   and Marathi, so that case asks Cloud Translate rather than picking one —
   answering a Marathi farmer in Hindi is a failure neither side can see.
3. **The plot's state**, from reverse geocoding. **West Bengal → Bengali,
   Maharashtra → Marathi, every other state → Hindi.** The weakest signal, which
   is why anything the farmer told us outranks it. Needs no API key — see the
   reverse geocoding section.

   English is deliberately unreachable from a location: a farmer gets it by
   asking for it or by writing in it, never because a pin landed somewhere
   unmapped.
4. **Marathi**, the demo district's language and the historical default, used
   only when there is no signal at all — including when `ground` is unreachable
   and the plot's state is genuinely unknown.

On the web app there is no phone number and so no stored preference: the
**location picker decides**, which is layers 3 and 4 alone. Each preset shows
the language it will produce before you submit.

**The rule that makes it safe.** The voice note is synthesised by that
language's TTS voice, and text in a script it does not read comes out as noise.
So every spoken script is checked against its target language and anything
foreign is stripped: Latin is foreign to Marathi, Hindi and Bengali; Devanagari
and Bengali are foreign to English. Where a value cannot be rendered safely it
is **omitted from the voice note** — the WhatsApp text still carries the exact
disease name and dose, which is what the farmer needs at the shop.

Adding a language is a data change: one row in `contracts/languages.py` and its
strings in `channel/services/phrasebook.py`. A completeness test fails if any
key, unit or disease name is missing, and another fails if a phrase uses a
script its own voice cannot read.

The officer dashboard and the public DPG feed stay English.

## Gemini API keys

`GEMINI_API_KEY`, plus optionally `GEMINI_API_KEY_1`, `_2`, `_3`… Requests are
spread **round-robin** across every configured key, with failover on top.

This matters because the free tier meters **per key, per model, per minute**. Two
consequences:

- **Spread, don't stick.** Round-robin gives roughly N× the per-minute headroom.
  Pinning to one key is what trips a rate limit while the others sit idle.
- **Don't race.** Sending the same request to all keys and taking the fastest
  would burn N× the quota to shave a queueing delay that barely exists — a
  diagnosis spends 4–8s inside the model. That spends the scarce resource to buy
  the cheap one.

A key that fails is put on **cooldown**, keyed by `(key, model)` because that is
how the quota is actually metered — a key spent on `gemini-3.6-flash` still
answers on `gemini-3.5-flash`.

What rotates is decided by one question: *would another key behave differently?*

| Error | | Behaviour |
|---|---|---|
| `429` quota | key-specific | rotate, 60s cooldown |
| `503` overloaded | transient | rotate, 60s cooldown |
| `403` project denied | **key-specific** | rotate, 30min cooldown, logged as an error |
| `404` model retired | same on every key | raise immediately |
| `400` bad request | same on every key | raise immediately |

`403` belongs with the rotating errors, not the fatal ones: it means *this
project* is denied, and the other keys are other projects. Grouping it with
`404` meant one denied key in four failed one diagnosis in four.

`GEMINI_MODEL` selects the model (default `gemini-3.6-flash`). It is pinned
rather than aliased, but configurable: `gemini-2.5-flash` was hardcoded here
until Google stopped serving it to new keys, at which point every diagnosis
turned into a silent escalation.

Search grounding needs a **billed** project — on a free key it returns 429 and
the tool ladder drops to function-calling only, which does work on the free tier.

`/health` on brain reports how many keys are loaded and which is active, showing
only the last four characters of each.

## Reverse geocoding (no key required)

A dropped pin becomes a real district, which selects the telemetry fallbacks,
the outbreak cluster, and the farmer's language. Two providers:

| `GEOCODER` | Uses | Needs |
|---|---|---|
| unset (default) | Google if `GOOGLE_MAPS_API_KEY` is set, else Nominatim | nothing |
| `nominatim` | OpenStreetMap Nominatim | nothing |
| `google` | Google Maps Geocoding | an API key + billing |
| `none` | no lookups; callers keep whatever district they passed | — |

**Nominatim is the default because the failure mode of requiring a key was the
bug this feature exists to fix**: with no key, every farmer was labelled Nashik.
It needs no key, no billing and no signup, and returns the Indian
`state_district` and `state` names this project already keys on — verified
against Nashik, Nagpur, Kolkata, Lucknow and Kochi.

It is rate limited to roughly one request per second, which the client honours
along with the identifying `User-Agent` their policy requires. Real volume is
far below that, since passports are cached by geohash for 7 days. Set a Maps key
for production traffic; it is picked up automatically.

Attribution (ODbL) travels in `PlotPassport.data_sources`, so the DPG feed
carries it to anyone consuming the data.

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
| `GOOGLE_MAPS_API_KEY` | Reverse geocoding still works, free, via OpenStreetMap Nominatim |
| `ENABLE_TRANSLATION` | The fallback voice script drops `action_text` rather than speaking it |
| `MEDIA_ARCHIVE_BUCKET` | Escalated photos are not retained for the review we promise |
| `ENABLE_TRANSLATION` | Voice notes still work in all four languages; the fallback template drops `action_text`, and a Devanagari message cannot be told apart as Hindi or Marathi |

`/health` on each service reports which of these are actually live.
