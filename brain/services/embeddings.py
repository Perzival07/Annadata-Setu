"""Embedding function shared by ingest and retrieval.

BRAIN.md §8 specifies `text-embedding-004`. Left to its default, ChromaDB
instead downloads all-MiniLM-L6-v2 as ONNX from S3 on first use — 79 MB on the
wire, 167 MB unpacked — and it does that lazily, so on Cloud Run it lands in the
first request after a cold start, over whatever network the demo is on. Nothing
in the image ships that model, so it would be fetched again on every new
instance.

The embedder used to build a collection and the one used to query it MUST match:
vectors from two different models are not comparable, and a mismatch does not
error — it silently returns the wrong chunks. Collections are therefore stamped
with the embedder that built them, and a mismatch falls back to built-in notes
rather than serving nonsense.
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger("brain.embeddings")

EMBED_MODEL = "text-embedding-004"
EMBEDDER_ID = f"google:{EMBED_MODEL}"


class GeminiEmbeddingFunction:
    """ChromaDB embedding function backed by the Gemini embeddings API."""

    def __init__(self, api_key: str, model: str = EMBED_MODEL):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @staticmethod
    def name() -> str:
        return "annadata_gemini_text_embedding_004"

    def __call__(self, input) -> List[List[float]]:
        if isinstance(input, str):
            input = [input]
        res = self._client.models.embed_content(model=self._model, contents=list(input))
        return [list(e.values) for e in res.embeddings]

    # Chroma persists and replays this to rebuild the function on load.
    def get_config(self) -> dict:
        return {"model": self._model}

    @classmethod
    def build_from_config(cls, config: dict) -> "GeminiEmbeddingFunction":
        return cls(api_key=os.getenv("GEMINI_API_KEY", ""), model=config.get("model", EMBED_MODEL))


def get_embedding_function() -> Optional[GeminiEmbeddingFunction]:
    """The configured embedder, or None when it cannot be built.

    None means "do not query the vector store" — never "quietly use a different
    model", which is what ChromaDB's default would do.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning(
            f"GEMINI_API_KEY is not set, so {EMBED_MODEL} embeddings are unavailable. "
            "Vector retrieval is disabled; built-in notes will be used."
        )
        return None
    try:
        return GeminiEmbeddingFunction(api_key=api_key)
    except Exception as e:
        logger.warning(f"Could not build the {EMBED_MODEL} embedding function: {e}")
        return None
