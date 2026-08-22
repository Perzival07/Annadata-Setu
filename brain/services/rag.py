import os
import logging
from typing import List, Dict

logger = logging.getLogger("brain.rag")

# Default fallback ICAR knowledge chunks for Maharashtra crops
FALLBACK_KNOWLEDGE = [
    {
        "crop": "Tomato",
        "disease": "Early Blight",
        "content": "Early Blight (Alternaria solani) in Tomato: Symptoms include dark concentric spots on lower leaves. High humidity (>80%) and warm temperatures accelerate spread. Recommended treatment: Spray Mancozeb 75% WP @ 2g/L or Chlorothalonil 75% WP @ 2g/L. Cost approx ₹300-400 per acre.",
        "source": "ICAR_Tomato_Package_of_Practices_2023.pdf"
    },
    {
        "crop": "Tomato",
        "disease": "Late Blight",
        "content": "Late Blight (Phytophthora infestans) in Tomato: Water-soaked lesions on leaves rapidly turning dark brown. Cool moist weather favors outbreak. Recommended treatment: Spray Cymoxanil + Mancozeb @ 2g/L or Metalaxyl + Mancozeb @ 2.5g/L. Cost approx ₹550 per acre.",
        "source": "ICAR_Tomato_Package_of_Practices_2023.pdf"
    },
    {
        "crop": "Tomato",
        "disease": "Nitrogen Deficiency",
        "content": "Nitrogen Deficiency in Tomato: General yellowing of older leaves starting from leaf tips. Abiotic condition — do NOT spray chemical fungicides. Treatment: Apply Neem-coated Urea @ 25kg/acre or Foliar spray of 1% 19:19:19 NPK. Cost approx ₹150.",
        "source": "ICAR_Soil_Health_Guide_2023.pdf"
    },
    {
        "crop": "Onion",
        "disease": "Purple Blotch",
        "content": "Purple Blotch (Alternaria porri) in Onion: Small water-soaked lesions developing white center with purple margin. Spray Mancozeb 75% WP @ 2.5g/L or Tebuconazole @ 1ml/L.",
        "source": "ICAR_Onion_Package_of_Practices_2023.pdf"
    }
]

class RAGService:
    def __init__(self, chroma_dir: str = "brain/data/chroma"):
        self.chroma_dir = chroma_dir
        self.collection = None
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            if os.path.exists(self.chroma_dir):
                client = chromadb.PersistentClient(path=self.chroma_dir)
                self.collection = client.get_or_create_collection(name="icar_package_of_practices")
                logger.info(f"ChromaDB initialized at {self.chroma_dir}")
        except Exception as e:
            logger.warning(f"ChromaDB initialization fallback mode: {e}")

    def retrieve_context(self, crop: str, query: str, top_k: int = 4) -> List[Dict[str, str]]:
        """Retrieve top_k ICAR knowledge chunks for given crop and query."""
        if self.collection and self.collection.count() > 0:
            try:
                results = self.collection.query(
                    query_texts=[f"{crop} {query}"],
                    n_results=top_k
                )
                if results and "documents" in results and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                    return [
                        {"content": doc, "source": meta.get("source", "ICAR_Manual.pdf")}
                        for doc, meta in zip(docs, metas)
                    ]
            except Exception as e:
                logger.warning(f"ChromaDB query failed, using keyword fallback: {e}")

        # Keyword matching fallback
        matching_chunks = []
        crop_lower = crop.lower()
        query_lower = query.lower()

        for chunk in FALLBACK_KNOWLEDGE:
            if chunk["crop"].lower() in crop_lower or crop_lower in chunk["crop"].lower():
                matching_chunks.append({
                    "content": chunk["content"],
                    "source": chunk["source"]
                })

        if not matching_chunks:
            matching_chunks = [{"content": chunk["content"], "source": chunk["source"]} for chunk in FALLBACK_KNOWLEDGE[:top_k]]

        return matching_chunks[:top_k]

rag_service = RAGService()
