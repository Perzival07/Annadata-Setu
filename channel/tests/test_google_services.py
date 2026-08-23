"""Tests for translation on the voice path and the escalation photo archive.

The invariant under test is the one channel/services/marathi.py exists to
protect: nothing in Latin script reaches the mr-IN voice. Cloud Translate makes
the fallback script better by recovering action_text — but it is a
general-purpose translator that passes chemical names, percentages and product
codes straight through, so its output is checked, not trusted.
"""

import asyncio
import unittest
from unittest import mock

from contracts.fallbacks import unavailable_diagnosis
from contracts.models import Diagnosis
from channel.services import media as media_module
from channel.services.composer import composer_service
from channel.services.marathi import has_latin_script
from channel.services.media import MediaArchiveService, _sender_ref
from channel.services.translate import TranslateService


def run(coro):
    return asyncio.run(coro)


def _diagnosis(**overrides) -> Diagnosis:
    base = dict(
        disease_name="Early Blight",
        confidence=0.88,
        differentials=[],
        is_action_needed=True,
        action_text="Spray in the evening and avoid overhead irrigation.",
        dosage="2g per litre",
        estimated_cost_inr=340,
        urgency_hours=48,
        escalate_to_human=False,
        reasoning_context=[],
        sources=[],
    )
    base.update(overrides)
    return Diagnosis(**base)


class TranslationGuardTest(unittest.TestCase):
    def setUp(self):
        self.svc = TranslateService.__new__(TranslateService)
        self.svc.client = mock.Mock()
        self.svc.parent = "projects/p/locations/global"

    def _returns(self, text):
        self.svc.client.translate_text.return_value = mock.Mock(
            translations=[mock.Mock(translated_text=text)]
        )

    def test_marathi_output_is_kept(self):
        self._returns("संध्याकाळी फवारणी करा.")
        self.assertEqual(run(self.svc.to_marathi("Spray in the evening.")), "संध्याकाळी फवारणी करा.")

    def test_output_with_latin_script_is_discarded(self):
        """Translate leaves 'Mancozeb 75% WP' alone. Half-translated is unusable."""
        self._returns("Mancozeb ७५% WP ची फवारणी करा.")
        self.assertIsNone(run(self.svc.to_marathi("Spray Mancozeb 75% WP.")))

    def test_empty_input_is_not_sent(self):
        self.assertIsNone(run(self.svc.to_marathi("")))
        self.assertIsNone(run(self.svc.to_marathi("   ")))
        self.svc.client.translate_text.assert_not_called()

    def test_unconfigured_client_returns_none(self):
        self.svc.client = None
        self.assertIsNone(run(self.svc.to_marathi("Spray in the evening.")))

    def test_api_failure_returns_none(self):
        self.svc.client.translate_text.side_effect = RuntimeError("quota exceeded")
        self.assertIsNone(run(self.svc.to_marathi("Spray in the evening.")))

    def test_empty_translation_list_returns_none(self):
        self.svc.client.translate_text.return_value = mock.Mock(translations=[])
        self.assertIsNone(run(self.svc.to_marathi("Spray in the evening.")))


class TranslatedScriptTest(unittest.TestCase):
    """The composer's contract with translated text."""

    def test_translated_action_is_spoken(self):
        script = composer_service.compose_marathi_script(
            _diagnosis(), action_mr="संध्याकाळी फवारणी करा"
        )
        self.assertIn("संध्याकाळी फवारणी करा", script)
        self.assertFalse(has_latin_script(script))

    def test_script_without_translation_is_unchanged(self):
        """Translation off must leave the script exactly as it was."""
        self.assertEqual(
            composer_service.compose_marathi_script(_diagnosis()),
            composer_service.compose_marathi_script(_diagnosis(), action_mr=None),
        )

    def test_translated_action_on_the_dont_spray_path(self):
        script = composer_service.compose_marathi_script(
            _diagnosis(is_action_needed=False, dosage=None),
            action_mr="खत द्या",
        )
        self.assertIn("खत द्या", script)
        self.assertIn("फवारणी करण्याची गरज नाही", script)
        self.assertFalse(has_latin_script(script))

    def test_latin_action_cannot_reach_the_voice(self):
        """Belt and braces: even if a caller passes English, nothing Latin survives."""
        script = composer_service.compose_marathi_script(
            _diagnosis(), action_mr="Spray Mancozeb now"
        )
        self.assertFalse(has_latin_script(script))

    def test_escalation_ignores_translated_action(self):
        """An escalation says 'do not spray'. It must not gain advice."""
        script = composer_service.compose_marathi_script(
            unavailable_diagnosis(), action_mr="फवारणी करा"
        )
        self.assertNotIn("फवारणी करा", script)
        self.assertIn("फवारणी करू नका", script)


class EscalationArchiveTest(unittest.TestCase):
    def setUp(self):
        self.svc = MediaArchiveService.__new__(MediaArchiveService)
        self.svc.bucket = mock.Mock()
        self.passport = mock.Mock(
            plot_id="hash_24aebeab", geohash="tes3z0k", district="Nashik", inferred_crop="Tomato"
        )

    def test_object_path_does_not_contain_the_phone_number(self):
        captured = {}

        def upload(path, image_bytes, metadata):
            captured["path"] = path
            return f"gs://b/{path}"

        self.svc._upload_blocking = upload
        run(self.svc.archive_for_review(
            b"jpegbytes", "+919876543210", self.passport, unavailable_diagnosis()
        ))
        self.assertNotIn("919876543210", captured["path"])
        self.assertNotIn("9876543210", captured["path"])

    def test_sender_ref_is_stable_and_salted(self):
        with mock.patch.object(media_module, "HASH_SALT", "salt-a"):
            a = _sender_ref("+919876543210")
            self.assertEqual(a, _sender_ref("+919876543210"))
        with mock.patch.object(media_module, "HASH_SALT", "salt-b"):
            self.assertNotEqual(a, _sender_ref("+919876543210"))

    def test_no_bytes_is_a_no_op(self):
        self.assertIsNone(run(self.svc.archive_for_review(
            None, "+91987", self.passport, unavailable_diagnosis()
        )))

    def test_unconfigured_archive_is_a_no_op(self):
        self.svc.bucket = None
        self.assertIsNone(run(self.svc.archive_for_review(
            b"x", "+91987", self.passport, unavailable_diagnosis()
        )))

    def test_upload_failure_does_not_raise(self):
        """The farmer already has their reply; a storage outage must not surface."""
        self.svc._upload_blocking = mock.Mock(side_effect=RuntimeError("bucket gone"))
        self.assertIsNone(run(self.svc.archive_for_review(
            b"x", "+91987", self.passport, unavailable_diagnosis()
        )))


if __name__ == "__main__":
    unittest.main()
