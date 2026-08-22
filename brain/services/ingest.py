import os
import glob
import logging
from typing import List

logger = logging.getLogger("brain.ingest")

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Split long text into overlapping chunks of approximately chunk_size characters."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks

def ingest_pdfs(pdf_dir: str = "brain/data/icar_pdfs", chroma_dir: str = "brain/data/chroma"):
    """Parse ICAR PDFs, chunk text, and populate ChromaDB collection."""
    try:
        import pypdf
        import chromadb
    except ImportError as e:
        logger.error(f"Missing dependency for PDF ingestion: {e}")
        return

    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {pdf_dir}")
        return

    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(name="icar_package_of_practices")

    total_chunks = 0
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        try:
            reader = pypdf.PdfReader(pdf_path)
            full_text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + "\n"

            chunks = chunk_text(full_text)
            ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [{"source": filename} for _ in chunks]

            collection.add(
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
            total_chunks += len(chunks)
            logger.info(f"Ingested {len(chunks)} chunks from {filename}")
        except Exception as e:
            logger.error(f"Failed to ingest {filename}: {e}")

    logger.info(f"Ingestion complete. Total chunks in ChromaDB: {total_chunks}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_pdfs()
