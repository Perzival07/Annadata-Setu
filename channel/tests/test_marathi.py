"""The spoken advisory must be speakable by an mr-IN voice.

The defect: compose_marathi_script interpolated the raw Diagnosis fields — which
arrive in English — into Marathi sentence frames. A typical script was ~45%
Latin script, including the whole of action_text, handed to a Marathi TTS voice.
"""

import re
import unittest

from contracts.models import Diagnosis
from contracts.fallbacks import unavailable_diagnosis
from channel.services.composer import composer_service
from channel.services.marathi import (
    disease_in_marathi,
    dosage_in_marathi,
    to_devanagari_digits,
    has_latin_script,
    strip_to_speakable,
)

LATIN = re.compile(r"[A-Za-z]")


def _diagnosis(**over):
    base = dict(
        disease_name="Early Blight (Alternaria solani)", confidence=0.88,
        differentials=["Late Blight"], is_action_needed=True,
        action_text="Spray Mancozeb 75% WP tomorrow morning before expected rain on Thursday.",
        dosage="2g per litre of water", estimated_cost_inr=340, urgency_hours=24,
        escalate_to_human=False, reasoning_context=["RH >85%"], sources=[],
    )
    base.update(over)
    return Diagnosis(**base)


class SpokenScriptTest(unittest.TestCase):
    def assertSpeakable(self, script):
        found = LATIN.findall(script)
        self.assertEqual(
            found, [],
            f"script contains Latin script an mr-IN voice cannot pronounce: {script!r}",
        )
        self.assertTrue(script.strip())
        self.assertNotIn("..", script, "doubled sentence terminator")

    def test_treatment_script_is_devanagari_only(self):
        self.assertSpeakable(composer_service.compose_marathi_script(_diagnosis()))

    def test_dont_spray_script_is_devanagari_only(self):
        d = _diagnosis(disease_name="Nitrogen Deficiency", is_action_needed=False,
                       dosage=None, action_text="No fungicide needed.")
        script = composer_service.compose_marathi_script(d)
        self.assertSpeakable(script)
        self.assertIn("गरज नाही", script)

    def test_escalation_script_is_devanagari_only_and_forbids_spraying(self):
        script = composer_service.compose_marathi_script(unavailable_diagnosis())
        self.assertSpeakable(script)
        self.assertIn("फवारणी करू नका", script)

    def test_unknown_disease_never_leaks_its_english_name(self):
        """A disease with no Marathi mapping must not be spoken in English."""
        d = _diagnosis(disease_name="Tuta absoluta leafminer infestation")
        script = composer_service.compose_marathi_script(d)
        self.assertSpeakable(script)
        self.assertNotIn("Tuta", script)

    def test_unparseable_dosage_never_leaks(self):
        d = _diagnosis(dosage="apply as per manufacturer label instructions")
        script = composer_service.compose_marathi_script(d)
        self.assertSpeakable(script)
        self.assertIn("पाकिटावर", script)

    def test_escalated_script_states_no_cost_or_dose(self):
        script = composer_service.compose_marathi_script(unavailable_diagnosis())
        self.assertNotIn("₹", script)
        self.assertNotIn("ग्रॅम", script)


class RenderingHelpersTest(unittest.TestCase):
    def test_botanical_binomial_is_dropped(self):
        self.assertEqual(disease_in_marathi("Early Blight (Alternaria solani)"),
                         disease_in_marathi("Early Blight"))

    def test_unmapped_disease_returns_none_rather_than_english(self):
        self.assertIsNone(disease_in_marathi("Some Unmapped Condition"))
        self.assertIsNone(disease_in_marathi(""))

    def test_dosage_patterns(self):
        self.assertEqual(dosage_in_marathi("2g per litre of water"), "१ लिटर पाण्यात २ ग्रॅम")
        self.assertEqual(dosage_in_marathi("2.5 g/L"), "१ लिटर पाण्यात २.५ ग्रॅम")
        self.assertEqual(dosage_in_marathi("1ml/L"), "१ लिटर पाण्यात १ मिली")
        self.assertIsNone(dosage_in_marathi("as per label"))
        self.assertIsNone(dosage_in_marathi(None))

    def test_digits_become_devanagari(self):
        self.assertEqual(to_devanagari_digits("₹340 in 24 hours"), "₹३४० in २४ hours")

    def test_strip_guard_removes_latin_runs(self):
        self.assertFalse(has_latin_script("नमस्कार. फवारणी करा."))
        self.assertTrue(has_latin_script("नमस्कार Spray now."))
        self.assertFalse(has_latin_script(strip_to_speakable("नमस्कार Spray Mancozeb आता.")))


if __name__ == "__main__":
    unittest.main()
