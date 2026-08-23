"""Evaluation suite for the diagnosis service.

The accuracy half (15 photos → expected labels, BRAIN.md §11) needs a live
GEMINI_API_KEY and the photo set; it is skipped without them. What always runs
is the safety half: what the service returns when it cannot answer.
"""

import asyncio
import json
import os
import unittest
from unittest import mock

from contracts.mock_data import PASSPORT, DIAGNOSIS as FIXTURE
from brain.services import gemini as gemini_module
from brain.services.gemini import GeminiService, CONFIDENCE_ESCALATION_THRESHOLD

# BRAIN.md §11 (10:30): iterate the prompt against these until they hold.
TEST_CASES = [
    {"name": "Tomato Early Blight - Severe", "crop": "Tomato",
     "expected_disease": "Early Blight", "expected_action_needed": True},
    {"name": "Tomato Nitrogen Deficiency - Abiotic Don't Spray", "crop": "Tomato",
     "expected_disease": "Nitrogen Deficiency", "expected_action_needed": False},
    {"name": "Onion Purple Blotch", "crop": "Onion",
     "expected_disease": "Purple Blotch", "expected_action_needed": True},
]


def _response(**overrides):
    payload = {
        "disease_name": "Early Blight", "confidence": 0.88, "differentials": ["Late Blight"],
        "is_action_needed": True, "action_text": "Spray tomorrow morning.",
        "dosage": "2g per litre", "estimated_cost_inr": 340, "urgency_hours": 24,
        "escalate_to_human": False, "reasoning_context": ["RH >85%"], "sources": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


class FakeClient:
    def __init__(self, text):
        self.models = mock.Mock()
        self.models.generate_content.return_value = mock.Mock(text=text)


class DiagnosisSafetyTest(unittest.TestCase):
    """A failed diagnosis must never be dressed up as a confident one."""

    def _diagnose(self, service):
        return asyncio.run(service.diagnose_leaf(image_url=None, image_bytes=b"img", passport=PASSPORT))

    def _service(self, text):
        svc = GeminiService.__new__(GeminiService)
        svc.client = FakeClient(text)
        return svc

    def test_missing_client_escalates_instead_of_returning_the_fixture(self):
        svc = GeminiService.__new__(GeminiService)
        svc.client = None
        with mock.patch.object(gemini_module, "MOCK", False):
            d = self._diagnose(svc)
        self.assertTrue(d.escalate_to_human)
        self.assertNotEqual(d.disease_name, FIXTURE.disease_name)
        self.assertIsNone(d.dosage)
        self.assertEqual(d.estimated_cost_inr, 0)

    def test_unparseable_response_escalates(self):
        d = self._diagnose(self._service("sorry, I can't help with that"))
        self.assertTrue(d.escalate_to_human)
        self.assertIsNone(d.dosage)

    def test_empty_response_escalates(self):
        d = self._diagnose(self._service(""))
        self.assertTrue(d.escalate_to_human)

    def test_low_confidence_escalates_even_when_the_model_says_otherwise(self):
        d = self._diagnose(self._service(_response(confidence=0.41, escalate_to_human=False)))
        self.assertTrue(d.escalate_to_human)

    def test_escalated_diagnosis_carries_no_prescription(self):
        """Any renderer that forgets to check the flag must still find no dose to show."""
        d = self._diagnose(self._service(_response(confidence=0.30)))
        self.assertIsNone(d.dosage)
        self.assertEqual(d.estimated_cost_inr, 0)

    def test_confident_diagnosis_passes_through_intact(self):
        d = self._diagnose(self._service(_response(confidence=0.88)))
        self.assertFalse(d.escalate_to_human)
        self.assertEqual(d.dosage, "2g per litre")
        self.assertGreaterEqual(d.confidence, CONFIDENCE_ESCALATION_THRESHOLD)


@unittest.skipUnless(
    os.getenv("GEMINI_API_KEY") and os.getenv("EVAL_PHOTO_DIR"),
    "Set GEMINI_API_KEY and EVAL_PHOTO_DIR to run the live photo evaluation.",
)
class LivePhotoEvalTest(unittest.TestCase):
    def test_expected_labels(self):
        photo_dir = os.getenv("EVAL_PHOTO_DIR")
        from brain.services.gemini import gemini_service
        for case in TEST_CASES:
            path = os.path.join(photo_dir, f"{case['name']}.jpg")
            if not os.path.exists(path):
                self.skipTest(f"Missing evaluation photo: {path}")
            with open(path, "rb") as f:
                image_bytes = f.read()
            d = asyncio.run(gemini_service.diagnose_leaf(None, image_bytes, PASSPORT))
            with self.subTest(case=case["name"]):
                self.assertEqual(d.is_action_needed, case["expected_action_needed"])
                self.assertIn(case["expected_disease"].lower(), d.disease_name.lower())


if __name__ == "__main__":
    unittest.main()
