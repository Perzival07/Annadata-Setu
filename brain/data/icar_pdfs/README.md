# Reference PDFs (not committed)

Put the agronomic reference PDFs here — the ICAR Package of Practices documents
for your crop and district — then build the vector store:

```bash
python -m brain.services.ingest --reset
git add brain/data/chroma && git commit -m "[P2] ingest reference corpus"
```

No API key is required — embeddings use ChromaDB's local `all-MiniLM-L6-v2`,
baked into the image by `brain/Dockerfile`. See [`SOURCES.md`](./SOURCES.md) for
what is currently indexed and where it came from.

The PDFs themselves are gitignored and excluded from the image. Only the
resulting `brain/data/chroma/` store ships.

## Why this matters

Until the store is populated, `brain/services/rag.py` answers from a small set of
built-in notes and **`sources[]` comes back empty** — no advisory cites a
document, because no document was retrieved. That is deliberate: an earlier
version labelled the built-in notes with ICAR filenames that exist nowhere in
this repo, putting a citation on the farmer's message that nobody could check.

`GET /health` on the brain service reports `"status": "degraded"` and
`"retrieval_mode": "builtin_only"` whenever the corpus is empty.
