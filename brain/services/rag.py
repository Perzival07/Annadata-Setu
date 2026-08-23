import logging
import os
from typing import Dict, List, Optional

from brain.services.embeddings import EMBEDDER_ID, get_embedding_function

logger = logging.getLogger("brain.rag")

CHROMA_DIR = os.getenv("CHROMA_DIR", "brain/data/chroma")
COLLECTION_NAME = "icar_package_of_practices"

# Provenance markers. These decide whether a chunk may be cited to the farmer.
FROM_CORPUS = "corpus"    # retrieved from the ingested document store
FROM_BUILTIN = "builtin"  # the small safety net below — NOT a citable document

# A minimal built-in reference so the service still returns sane agronomy when no
# corpus has been ingested. It is deliberately NOT labelled with document
# filenames: attributing these lines to an ICAR PDF that was never ingested puts
# a citation the farmer cannot check on the bottom of their advisory.
BUILTIN_KNOWLEDGE = [
    {
        "crop": "Tomato",
        "disease": "Early Blight",
        "content": "Early Blight (Alternaria solani) in Tomato: dark concentric spots on lower leaves. High humidity (>80%) and warm temperatures accelerate spread. Commonly managed with Mancozeb 75% WP @ 2g/L or Chlorothalonil 75% WP @ 2g/L. Approx ₹300-400 per acre.",
    },
    {
        "crop": "Tomato",
        "disease": "Late Blight",
        "content": "Late Blight (Phytophthora infestans) in Tomato: water-soaked lesions turning dark brown. Cool moist weather favours outbreak. Commonly managed with Cymoxanil + Mancozeb @ 2g/L or Metalaxyl + Mancozeb @ 2.5g/L. Approx ₹550 per acre.",
    },
    {
        "crop": "Tomato",
        "disease": "Nitrogen Deficiency",
        "content": "Nitrogen Deficiency in Tomato: general yellowing of older leaves from the tips. Abiotic — do NOT spray fungicides. Managed with neem-coated urea @ 25kg/acre or a 1% 19:19:19 NPK foliar spray. Approx ₹150.",
    },
    {
        "crop": "Onion",
        "disease": "Purple Blotch",
        "content": "Purple Blotch (Alternaria porri) in Onion: small water-soaked lesions developing a white centre with a purple margin. Commonly managed with Mancozeb 75% WP @ 2.5g/L or Tebuconazole @ 1ml/L.",
    },
]

# Kept for callers that still import the old name.
FALLBACK_KNOWLEDGE = BUILTIN_KNOWLEDGE


class RAGService:
    def __init__(self, chroma_dir: str = CHROMA_DIR):
        self.chroma_dir = chroma_dir
        self.collection = None
        self.embedder_mismatch: Optional[str] = None
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            if not os.path.exists(self.chroma_dir):
                logger.warning(
                    f"No ChromaDB store at {self.chroma_dir}. Retrieval will use built-in "
                    f"notes only and no document will be cited."
                )
                return
            client = chromadb.PersistentClient(path=self.chroma_dir)
            embed_fn = get_embedding_function()
            if embed_fn is None:
                logger.warning(
                    "No embedding function available — vector retrieval disabled, "
                    "built-in notes only."
                )
                return

            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=embed_fn,
                metadata={"embedder": EMBEDDER_ID},
            )

            # Vectors from two different models are not comparable, and querying
            # across them returns plausible-looking wrong chunks rather than an
            # error. Refuse instead.
            built_with = (collection.metadata or {}).get("embedder")
            if built_with and built_with != EMBEDDER_ID:
                logger.error(
                    f"Store at {self.chroma_dir} was built with {built_with!r} but this "
                    f"service embeds with {EMBEDDER_ID!r}. Refusing to query it — "
                    f"re-run `python -m brain.services.ingest --reset`."
                )
                self.embedder_mismatch = built_with
                return

            self.collection = collection
            count = self.collection.count()
            if count == 0:
                # Loud, because the failure is otherwise invisible: retrieval keeps
                # working, just without any of the documents the pitch is built on.
                logger.warning(
                    "=" * 72 + "\n"
                    f"ChromaDB collection '{COLLECTION_NAME}' is EMPTY ({self.chroma_dir}).\n"
                    "RAG is running on built-in notes only. No advisory will cite a source.\n"
                    "Populate it with:  python -m brain.services.ingest\n"
                    "after placing the source PDFs in brain/data/icar_pdfs/.\n"
                    + "=" * 72
                )
            else:
                logger.info(f"ChromaDB ready at {self.chroma_dir}: {count} chunks indexed.")
        except Exception as e:
            # Chroma raises this when the persisted collection was built by a
            # different embedder. That is a real mismatch, not a transient
            # failure, and the operator needs the remedy rather than a stack trace.
            if "mbedding function" in str(e):
                self.embedder_mismatch = "default (ChromaDB built-in)"
                logger.error(
                    f"Store at {self.chroma_dir} was embedded with a different model than "
                    f"{EMBEDDER_ID}. Vectors from two models are not comparable, so retrieval "
                    f"is disabled. Rebuild it:  python -m brain.services.ingest --reset"
                )
            else:
                logger.warning(f"ChromaDB initialization failed, using built-in notes: {e}")

    @property
    def corpus_size(self) -> int:
        """Number of indexed chunks. Zero means nothing is citable."""
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0

    def status(self) -> Dict[str, object]:
        """Corpus health, surfaced on /health so a degraded demo is visible."""
        size = self.corpus_size
        status = {
            "chroma_dir": self.chroma_dir,
            "collection": COLLECTION_NAME,
            "embedder": EMBEDDER_ID,
            "indexed_chunks": size,
            "retrieval_mode": "corpus" if size else "builtin_only",
            "sources_citable": bool(size),
        }
        if self.embedder_mismatch:
            status["error"] = f"store built with {self.embedder_mismatch}, incompatible"
        return status

    def retrieve_context(self, crop: str, query: str, top_k: int = 4) -> List[Dict[str, Optional[str]]]:
        """Return up to top_k reference chunks, each tagged with its provenance.

        Only chunks tagged FROM_CORPUS carry a `source` that may be shown to the
        farmer. Built-in chunks return source=None so a caller cannot accidentally
        cite them as a document.
        """
        if self.corpus_size > 0:
            try:
                results = self.collection.query(query_texts=[f"{crop} {query}"], n_results=top_k)
                docs = (results.get("documents") or [[]])[0]
                if docs:
                    metas = (results.get("metadatas") or [[{}] * len(docs)])[0]
                    return [
                        {
                            "content": doc,
                            "source": (meta or {}).get("source"),
                            "provenance": FROM_CORPUS,
                        }
                        for doc, meta in zip(docs, metas)
                    ]
            except Exception as e:
                logger.warning(f"ChromaDB query failed, using built-in notes: {e}")

        crop_lower = (crop or "").lower()
        matching = [
            c for c in BUILTIN_KNOWLEDGE
            if c["crop"].lower() in crop_lower or crop_lower in c["crop"].lower()
        ]
        if not matching:
            matching = BUILTIN_KNOWLEDGE[:top_k]

        return [
            {"content": c["content"], "source": None, "provenance": FROM_BUILTIN}
            for c in matching[:top_k]
        ]


rag_service = RAGService()
