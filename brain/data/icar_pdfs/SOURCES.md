# Corpus provenance

The PDFs themselves are gitignored (they are large and we do not redistribute
them). Only the embeddings in `brain/data/chroma/` ship. This file records where
each came from, because `sources[]` in every advisory names these filenames and
they are published on the outbreak feed — an adopter must be able to trace a
recommendation back to its document.

| Filename | Publisher | Pages | Source |
|---|---|---|---|
| `ICAR_Kharif_Agro_Advisories_2025.pdf` | ICAR, New Delhi | 310 | https://icar.org.in/sites/default/files/Circulars/ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf |
| `GIZ_Good_Agricultural_Practices_Tomato_Karnataka.pdf` | GIZ / SNRD Asia | 98 | https://snrd-asia.org/wp-content/uploads/2024/07/27-Good-agricultural-practices-in-Tomato-Cultivation-%E2%80%93-A-technical-manual-for-Karnataka.pdf |
| `TNAU_Tomato_Origin_Varieties_Package_of_Practices.pdf` | TNAU (eAgri) | 18 | http://eagri.org/eagri50/HORT281/pdf/lec04.pdf |
| `TNAU_Onion_Package_of_Practices.pdf` | TNAU (eAgri) | 15 | http://eagri.org/eagri50/HORT281/pdf/lec15.pdf |
| `TNAU_Pests_of_Onion_Garlic_Turmeric_Ginger.pdf` | TNAU (eAgri) | 11 | http://www.eagri.org/eagri50/ENTO331/lecture27/lec027.pdf |

452 pages, 716 indexed chunks.

## Caveats worth knowing before this is presented as authoritative

- **This is 5 documents, not the ~30 BRAIN.md §10 calls for.** ICAR's KVK
  repository (`kvk.icar.gov.in`) and the Directorate of Onion and Garlic Research
  (`dogr.icar.gov.in`) were unreachable when this corpus was assembled; DOGR is
  in Pune and is the most directly relevant onion source for Nashik. Add them
  when reachable and re-run ingest.
- **Licensing is mixed and was not individually verified.** These are publicly
  downloadable government and development-agency extension materials. That is
  fine for a hackathon corpus, but the DPG claim covers *our* schemas and code
  under Apache 2.0 — it does not relicense these documents.
- **Only two are ICAR-published.** The TNAU material is Tamil Nadu extension
  content and the GIZ manual is written for Karnataka, so neither is
  Maharashtra-specific. Retrieval may surface agronomy calibrated for a
  different state.

## Rebuilding

```bash
python -m brain.services.ingest --reset
git add brain/data/chroma && git commit -m "[P2] re-ingest reference corpus"
```

No API key is needed: embeddings use ChromaDB's local `all-MiniLM-L6-v2`, which
`brain/Dockerfile` bakes into the image.
