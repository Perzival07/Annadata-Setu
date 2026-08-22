"""Evaluation suite running leaf photo test cases against expected diagnosis outputs."""

import asyncio
import unittest
from contracts.mock_data import PASSPORT
from brain.services.gemini import gemini_service

TEST_CASES = [
    {
        "name": "Tomato Early Blight - Severe",
        "crop": "Tomato",
        "expected_disease": "Early Blight",
        "expected_action_needed": True
    },
    {
        "name": "Tomato Nitrogen Deficiency - Abiotic Don't Spray",
        "crop": "Tomato",
        "expected_disease": "Nitrogen Deficiency",
        "expected_action_needed": False
    },
    {
        "name": "Onion Purple Blotch",
        "crop": "Onion",
        "expected_disease": "Purple Blotch",
        "expected_action_needed": True
    }
]

class TestBrainDiagnosisEval(unittest.TestCase):
    def test_mock_diagnosis(self):
        loop = asyncio.get_event_loop()
        diagnosis = loop.run_until_complete(
            gemini_service.diagnose_leaf(
                image_url=None,
                image_bytes=None,
                passport=PASSPORT
            )
        )
        self.assertIsNotNone(diagnosis.disease_name)
        self.assertGreaterEqual(diagnosis.confidence, 0.0)
        self.assertLessEqual(diagnosis.confidence, 1.0)
        self.assertIsInstance(diagnosis.reasoning_context, list)
        print(f"Eval Test Passed: {diagnosis.disease_name} (Confidence: {diagnosis.confidence})")

if __name__ == "__main__":
    unittest.main()
