"""Embedding model shared by ingest and retrieval.

ChromaDB's built-in all-MiniLM-L6-v2 runs locally with no API key, which is why
it is used here rather than the text-embedding-004 named in BRAIN.md §8: the
demo has to work on venue wifi without depending on an embeddings API being
reachable per query.

The catch is that ChromaDB fetches the model lazily from S3 on first use —
79 MB on the wire, ~167 MB unpacked. Left alone, that download happens inside
the first request after a Cloud Run cold start, and repeats on every new
instance. brain/Dockerfile therefore warms it at build time so it ships in the
image; `model_is_baked()` reports whether that actually happened.

The embedder that builds a collection and the one that queries it MUST match.
Vectors from two models are not comparable, and querying across them does not
error — it returns plausible-looking wrong chunks. Collections are stamped with
EMBEDDER_ID and a mismatch disables retrieval rather than serving nonsense.
"""

import logging
import os

logger = logging.getLogger("brain.embeddings")

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDER_ID = f"chroma:{MODEL_NAME}"


def model_cache_path() -> str:
    """Where ChromaDB keeps the ONNX model for this process."""
    try:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        return ONNXMiniLM_L6_V2.DOWNLOAD_PATH
    except Exception:
        return os.path.expanduser(f"~/.cache/chroma/onnx_models/{MODEL_NAME}")


def model_is_baked() -> bool:
    """True when the model is already on disk, so no request will trigger a download."""
    path = model_cache_path()
    return os.path.isdir(path) and any(
        os.path.exists(os.path.join(path, f)) for f in ("onnx", "onnx.tar.gz")
    )


def warm_model() -> bool:
    """Download and unpack the model. Called from the Dockerfile at build time."""
    try:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        ONNXMiniLM_L6_V2()(["warm up the embedding model"])
        logger.info(f"Embedding model ready at {model_cache_path()}")
        return True
    except Exception as e:
        logger.error(f"Could not warm the embedding model: {e}")
        return False


def embedder_status() -> dict:
    return {
        "embedder": EMBEDDER_ID,
        "model_cached": model_is_baked(),
        "cache_path": model_cache_path(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(0 if warm_model() else 1)
