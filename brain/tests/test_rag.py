"""Tests for retrieval provenance and corpus health.

The defect these guard against: the service cited
ICAR_Tomato_Package_of_Practices_2023.pdf — a file that exists nowhere in this
repo — as the source of text hardcoded in rag.py. That citation reached the
farmer's WhatsApp message and the public outbreak feed.
"""

import json
import unittest
from unittest import mock

from brain.services import rag as rag_module
from brain.services.rag import RAGService, BUILTIN_KNOWLEDGE, FROM_BUILTIN, FROM_CORPUS
from brain.services.ingest import chunk_text, TARGET_CHARS, CHARS_PER_TOKEN


class BuiltinProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.svc = RAGService.__new__(RAGService)
        self.svc.chroma_dir = "/nonexistent"
        self.svc.collection = None
        self.svc.embedder_mismatch = None

    def test_builtin_chunks_are_never_attributed_to_a_document(self):
        for doc in self.svc.retrieve_context("Tomato", "early blight"):
            self.assertEqual(doc["provenance"], FROM_BUILTIN)
            self.assertIsNone(doc["source"], "built-in notes must not carry a filename")

    def test_no_builtin_entry_claims_a_pdf_filename(self):
        blob = json.dumps(BUILTIN_KNOWLEDGE)
        self.assertNotIn(".pdf", blob, "built-in knowledge must not name a document")

    def test_status_reports_degraded_when_empty(self):
        status = self.svc.status()
        self.assertEqual(status["retrieval_mode"], "builtin_only")
        self.assertFalse(status["sources_citable"])
        self.assertEqual(status["indexed_chunks"], 0)

    def test_unknown_crop_still_returns_something(self):
        docs = self.svc.retrieve_context("Dragonfruit", "leaf spot")
        self.assertTrue(docs)
        self.assertTrue(all(d["source"] is None for d in docs))


class CorpusProvenanceTest(unittest.TestCase):
    """A populated corpus is citable; a built-in fallback is not."""

    def test_corpus_hits_carry_their_source(self):
        svc = RAGService.__new__(RAGService)
        svc.chroma_dir = "/tmp/x"
        svc.embedder_mismatch = None
        svc.collection = mock.Mock()
        svc.collection.count.return_value = 12
        svc.collection.query.return_value = {
            "documents": [["chunk one", "chunk two"]],
            "metadatas": [[{"source": "Ref_A.pdf"}, {"source": "Ref_B.pdf"}]],
        }
        docs = svc.retrieve_context("Tomato", "early blight")
        self.assertEqual({d["provenance"] for d in docs}, {FROM_CORPUS})
        self.assertEqual(sorted(d["source"] for d in docs), ["Ref_A.pdf", "Ref_B.pdf"])

    def test_query_failure_degrades_to_uncited_builtin(self):
        svc = RAGService.__new__(RAGService)
        svc.chroma_dir = "/tmp/x"
        svc.embedder_mismatch = None
        svc.collection = mock.Mock()
        svc.collection.count.return_value = 12
        svc.collection.query.side_effect = RuntimeError("index unreadable")
        docs = svc.retrieve_context("Tomato", "early blight")
        self.assertEqual({d["provenance"] for d in docs}, {FROM_BUILTIN})
        self.assertTrue(all(d["source"] is None for d in docs))


class ChunkingTest(unittest.TestCase):
    """BRAIN.md §11 specifies ~800-token semantic chunks, not 800 characters."""

    def test_chunks_target_the_specified_token_size(self):
        para = ("Management of foliar disease under field conditions. "
                "Apply a protectant fungicide before the onset of rain. ") * 200
        chunks = chunk_text(para)
        self.assertTrue(chunks)
        for c in chunks:
            self.assertLessEqual(len(c), TARGET_CHARS * 1.6)
        longest_tokens = max(len(c) for c in chunks) // CHARS_PER_TOKEN
        self.assertGreater(longest_tokens, 300, "chunks are far below the ~800 token target")

    def test_chunks_end_on_a_boundary_not_mid_word(self):
        text = " ".join(f"Sentence number {i} about crop disease management." for i in range(400))
        for c in chunk_text(text):
            self.assertFalse(c.endswith(" "))
            # A boundary-respecting split never ends on a partial word.
            self.assertRegex(c[-1], r"[.\w]")

    def test_empty_input_is_handled(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   \n\n  "), [])


class CitationIntegrationTest(unittest.TestCase):
    """sources[] must reflect what was retrieved, not what the model wrote."""

    def _diagnose_with(self, rag_docs, model_sources):
        import asyncio
        from brain.services.gemini import GeminiService
        from contracts.mock_data import PASSPORT

        payload = {
            "disease_name": "Early Blight", "confidence": 0.88, "differentials": [],
            "is_action_needed": True, "action_text": "Spray.", "dosage": "2g/L",
            "estimated_cost_inr": 340, "urgency_hours": 24, "escalate_to_human": False,
            "reasoning_context": ["x"], "sources": model_sources,
        }
        class FakePool:
            """Stands in for the key pool (brain/services/genai_pool.GeminiPool)."""

            async def generate(self, *, model, contents, config):
                return mock.Mock(text=json.dumps(payload))

        svc = GeminiService.__new__(GeminiService)
        svc.client = FakePool()
        with mock.patch.object(rag_module.rag_service, "retrieve_context", return_value=rag_docs):
            return asyncio.run(svc.diagnose_leaf(None, b"img", PASSPORT))

    def test_builtin_retrieval_cites_nothing(self):
        docs = [{"content": "c", "source": None, "provenance": FROM_BUILTIN}]
        # Even when the model invents a citation, it must not be published.
        d = self._diagnose_with(docs, ["ICAR_Tomato_Package_of_Practices_2023.pdf"])
        self.assertEqual(d.sources, [])

    def test_corpus_retrieval_cites_the_retrieved_documents(self):
        docs = [{"content": "c", "source": "Ref_A.pdf", "provenance": FROM_CORPUS}]
        d = self._diagnose_with(docs, [])
        self.assertEqual(d.sources, ["Ref_A.pdf"])


if __name__ == "__main__":
    unittest.main()
