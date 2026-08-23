"""One-off: source PDFs -> semantic chunks -> ChromaDB.

Run locally, commit the resulting store, and it ships inside the image:

    python -m brain.services.ingest

BRAIN.md §11 (14:00) specifies semantic chunks of roughly 800 tokens. The
previous implementation chunked 800 *characters* — about 200 tokens, four times
too small — and split mid-sentence, so a retrieved chunk routinely cut a dosage
away from the disease it belonged to.
"""

import argparse
import glob
import logging
import os
import re
from typing import Dict, List

from brain.services.embeddings import EMBEDDER_ID, get_embedding_function

logger = logging.getLogger("brain.ingest")

PDF_DIR = os.getenv("ICAR_PDF_DIR", "brain/data/icar_pdfs")
CHROMA_DIR = os.getenv("CHROMA_DIR", "brain/data/chroma")
COLLECTION_NAME = "icar_package_of_practices"

TARGET_TOKENS = 800
OVERLAP_TOKENS = 100
# English prose averages ~4 characters per token; close enough to size chunks
# without pulling in a tokenizer the service does not otherwise need.
CHARS_PER_TOKEN = 4
TARGET_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, target_chars: int = TARGET_CHARS, overlap_chars: int = OVERLAP_CHARS) -> List[str]:
    """Split into ~target_chars chunks that end on a paragraph or sentence boundary."""
    text = re.sub(r"[ \t]+", " ", text or "").strip()
    if not text:
        return []

    # Paragraphs first; anything still oversized is split on sentence ends.
    units: List[str] = []
    for para in _PARAGRAPH.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= target_chars:
            units.append(para)
            continue
        buf = ""
        for sentence in _SENTENCE.split(para):
            if buf and len(buf) + len(sentence) + 1 > target_chars:
                units.append(buf.strip())
                buf = sentence
            else:
                buf = f"{buf} {sentence}".strip()
        if buf:
            units.append(buf.strip())

    chunks: List[str] = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) + 1 > target_chars:
            chunks.append(current.strip())
            # Carry a tail of the previous chunk so a table or dosage split
            # across a boundary is still retrievable from either side.
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{tail} {unit}".strip() if tail else unit
        else:
            current = f"{current} {unit}".strip() if current else unit
    if current:
        chunks.append(current.strip())

    return [c for c in chunks if len(c) > 40]


def extract_pdf_text(path: str) -> str:
    import pypdf
    reader = pypdf.PdfReader(path)
    pages = []
    for page in reader.pages:
        try:
            extracted = page.extract_text()
        except Exception as e:
            logger.warning(f"  page extraction failed in {os.path.basename(path)}: {e}")
            continue
        if extracted:
            pages.append(extracted)
    return "\n\n".join(pages)


def ingest_pdfs(pdf_dir: str = PDF_DIR, chroma_dir: str = CHROMA_DIR, reset: bool = False) -> int:
    """Index every PDF in pdf_dir. Returns the resulting chunk count."""
    try:
        import chromadb
        import pypdf  # noqa: F401  (checked here so the error names the missing dep)
    except ImportError as e:
        logger.error(f"Missing dependency for PDF ingestion: {e}")
        return 0

    pdf_files = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))
    if not pdf_files:
        logger.error(
            f"No PDFs in {pdf_dir}. Nothing to ingest — the collection will stay empty "
            f"and no advisory will be able to cite a source."
        )
        return 0

    embed_fn = get_embedding_function()
    if embed_fn is None:
        logger.error(
            "Cannot embed without GEMINI_API_KEY. Refusing to build the store with "
            "ChromaDB's default model — retrieval would then have to use that same "
            "model, which is not what BRAIN.md §8 specifies and pulls 167 MB at runtime."
        )
        return 0

    os.makedirs(chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info(f"Dropped existing collection '{COLLECTION_NAME}'.")
        except Exception:
            pass
    # Stamp the collection with the embedder that built it, so retrieval can
    # refuse to query vectors it cannot compare against.
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"embedder": EMBEDDER_ID},
    )

    total = 0
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        try:
            text = extract_pdf_text(pdf_path)
            if not text.strip():
                logger.warning(f"{filename}: no extractable text (scanned image?). Skipped.")
                continue

            chunks = chunk_text(text)
            if not chunks:
                logger.warning(f"{filename}: produced no chunks. Skipped.")
                continue

            # upsert, not add: add() silently skips ids that already exist, so
            # re-running after editing a PDF kept serving the stale chunks.
            collection.upsert(
                documents=chunks,
                metadatas=[{"source": filename, "chunk": i} for i in range(len(chunks))],
                ids=[f"{filename}::chunk::{i}" for i in range(len(chunks))],
            )
            total += len(chunks)
            avg = sum(len(c) for c in chunks) // len(chunks)
            logger.info(f"{filename}: {len(chunks)} chunks (avg ~{avg // CHARS_PER_TOKEN} tokens)")
        except Exception as e:
            logger.error(f"Failed to ingest {filename}: {e}")

    final = collection.count()
    logger.info(f"Ingestion complete: {total} chunks written, collection now holds {final}.")
    if final == 0:
        logger.error("Collection is still empty — retrieval will fall back to built-in notes.")
    return final


def main():
    parser = argparse.ArgumentParser(description="Index reference PDFs into ChromaDB.")
    parser.add_argument("--pdf-dir", default=PDF_DIR)
    parser.add_argument("--chroma-dir", default=CHROMA_DIR)
    parser.add_argument("--reset", action="store_true", help="Drop the collection before indexing.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    count = ingest_pdfs(args.pdf_dir, args.chroma_dir, reset=args.reset)
    raise SystemExit(0 if count else 1)


if __name__ == "__main__":
    main()
