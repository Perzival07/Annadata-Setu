"""Multi-language support: the registry, the guards, and resolution.

The property that matters most is the one that generalises the original
Marathi-only rule: a script must contain nothing the target voice cannot read.
"Cannot read" is relative to the target — Latin is foreign to Marathi, Hindi and
Bengali; Devanagari and Bengali are foreign to English. A test that only checked
"no Latin" would pass every English script by accident and fail all of them by
design.
"""

import asyncio
import re
import unittest
from unittest import mock

from contracts.fallbacks import unavailable_diagnosis
from contracts.languages import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    get,
    has_foreign_script,
    localize_digits,
    strip_to_speakable,
)
from contracts.models import Diagnosis
from channel.services import pipeline
from channel.services.composer import composer_service
from channel.services.languages import (
    detect_from_text,
    is_language_request,
    language_for_state,
    menu_position,
    parse_language_command,
)
from channel.services.phrasebook import DISEASE_NAMES, PHRASES, UNITS, language_menu
from channel.services.render import disease_name, dosage_phrase

ALL = list(LANGUAGES)


def run(coro):
    return asyncio.run(coro)


def _diagnosis(**over) -> Diagnosis:
    base = dict(
        disease_name="Early Blight (Alternaria solani)", confidence=0.88,
        differentials=["Late Blight"], is_action_needed=True,
        action_text="Spray Mancozeb 75% WP tomorrow morning before expected rain.",
        dosage="2g per litre of water", estimated_cost_inr=340, urgency_hours=24,
        escalate_to_human=False, reasoning_context=["RH >85%"], sources=[],
    )
    base.update(over)
    return Diagnosis(**base)


class RegistryCompletenessTest(unittest.TestCase):
    """Adding a language must be a data change that fails loudly if half-done."""

    def test_every_language_has_a_full_phrase_set(self):
        reference = PHRASES[DEFAULT_LANGUAGE]
        for code in ALL:
            self.assertIn(code, PHRASES, f"{code} has no phrases")
            for section, entries in reference.items():
                self.assertIn(section, PHRASES[code], f"{code} missing section {section}")
                if isinstance(entries, dict):
                    self.assertEqual(
                        set(entries), set(PHRASES[code][section]),
                        f"{code}.{section} keys differ from {DEFAULT_LANGUAGE}",
                    )

    def test_every_language_has_units_and_a_disease_table(self):
        for code in ALL:
            self.assertEqual(set(UNITS[code]), {"g", "ml", "l", "kg"}, code)
            self.assertIn(code, DISEASE_NAMES, code)

    def test_non_english_disease_tables_cover_the_same_diseases(self):
        reference = set(DISEASE_NAMES[DEFAULT_LANGUAGE])
        for code in ALL:
            if get(code).script == "latin":
                continue  # English passes the name through; no table needed.
            self.assertEqual(set(DISEASE_NAMES[code]), reference, f"{code} disease table differs")

    def test_no_phrase_uses_a_script_its_own_voice_cannot_read(self):
        """The phrasebook must obey the rule it exists to enforce."""
        for code in ALL:
            for key in ("subject_unknown", "dose_unknown", "escalation", "treatment", "dont_spray"):
                text = PHRASES[code]["voice"][key]
                # Strip the {placeholders}, which are ASCII by necessity.
                bare = re.sub(r"\{\w+\}", "", text)
                self.assertFalse(
                    has_foreign_script(bare, code),
                    f"{code}.voice.{key} contains script a {get(code).bcp47} voice cannot read",
                )

    def test_menu_numbering_matches_the_parser(self):
        """'reply 3' must mean the same language in the menu and in the parser."""
        menu = language_menu()
        for code in ALL:
            position = menu_position(code)
            self.assertEqual(parse_language_command(str(position)), code)
            self.assertIn(LANGUAGES[code].endonym, menu)


class ScriptGuardTest(unittest.TestCase):
    """The generalisation of has_latin_script."""

    def test_foreign_is_relative_to_the_target(self):
        self.assertTrue(has_foreign_script("नमस्कार Spray now", "mr"))
        self.assertFalse(has_foreign_script("Spray now", "en"))
        self.assertTrue(has_foreign_script("Spray नमस्कार", "en"))
        self.assertTrue(has_foreign_script("নমস্কার नमस्कार", "bn"))
        self.assertFalse(has_foreign_script("নমস্কার ভালো", "bn"))

    def test_the_indic_danda_is_shared_punctuation_not_devanagari(self):
        """U+0964 ends sentences in Bengali as well as Hindi and Marathi.

        Unicode files it under Devanagari, so treating that whole block as
        foreign to Bengali rejected every correctly punctuated Bengali script
        Gemini produced — the voice note silently downgraded to the template.
        """
        bengali = "নমস্কার। আপনার টমেটো ফসলে আগাম ধসা রোগ দেখা দিয়েছে।"
        self.assertFalse(has_foreign_script(bengali, "bn"))
        self.assertEqual(strip_to_speakable(bengali, "bn"), bengali)
        self.assertFalse(has_foreign_script("नमस्ते। आपकी फसल पर रोग है।", "hi"))

    def test_real_devanagari_is_still_foreign_to_bengali(self):
        """The danda carve-out must not blind the guard to actual Devanagari."""
        self.assertTrue(has_foreign_script("নমস্কার আপকী फसल पर", "bn"))

    def test_english_is_not_stripped_of_itself(self):
        """The old guard would have deleted every English script entirely."""
        text = "Spray in the evening and avoid overhead irrigation."
        self.assertEqual(strip_to_speakable(text, "en"), text)

    def test_digits_follow_the_language(self):
        self.assertEqual(localize_digits("340", "mr"), "३४०")
        self.assertEqual(localize_digits("340", "hi"), "३४०")
        self.assertEqual(localize_digits("340", "bn"), "৩৪০")
        self.assertEqual(localize_digits("340", "en"), "340")

    def test_unknown_code_degrades_to_the_default(self):
        self.assertEqual(get("kl").code, DEFAULT_LANGUAGE)
        self.assertEqual(get(None).code, DEFAULT_LANGUAGE)
        self.assertEqual(get("bn-IN").code, "bn")


class SpokenScriptTest(unittest.TestCase):
    """Every language's script must be speakable by that language's voice."""

    def assertSpeakable(self, script, code):
        self.assertTrue(script.strip(), f"{code}: empty script")
        self.assertFalse(
            has_foreign_script(script, code),
            f"{code}: script contains text a {get(code).bcp47} voice cannot read: {script!r}",
        )
        self.assertNotIn("..", script, f"{code}: doubled sentence terminator")

    def test_treatment_script_in_every_language(self):
        for code in ALL:
            self.assertSpeakable(composer_service.compose_voice_script(_diagnosis(), code), code)

    def test_dont_spray_script_in_every_language(self):
        d = _diagnosis(disease_name="Nitrogen Deficiency", is_action_needed=False, dosage=None)
        for code in ALL:
            self.assertSpeakable(composer_service.compose_voice_script(d, code), code)

    def test_escalation_script_in_every_language_states_no_dose_or_cost(self):
        for code in ALL:
            script = composer_service.compose_voice_script(unavailable_diagnosis(), code)
            self.assertSpeakable(script, code)
            self.assertNotIn("₹", script, f"{code}: escalation named a cost")
            # The cost in this language's own digits — "340" would never appear
            # verbatim in a Devanagari script even if the cost were spoken.
            self.assertNotIn(
                localize_digits("340", code), script, f"{code}: escalation named a cost"
            )

    def test_unmapped_disease_never_leaks_into_a_non_latin_script(self):
        d = _diagnosis(disease_name="Tuta absoluta leafminer infestation")
        for code in ALL:
            script = composer_service.compose_voice_script(d, code)
            self.assertSpeakable(script, code)
            if get(code).script != "latin":
                self.assertNotIn("Tuta", script)

    def test_translated_action_is_spoken_in_every_language(self):
        samples = {
            "mr": "संध्याकाळी फवारणी करा", "hi": "शाम को छिड़काव करें",
            "bn": "সন্ধ্যায় স্প্রে করুন", "en": "Spray in the evening",
        }
        for code, advice in samples.items():
            script = composer_service.compose_voice_script(
                _diagnosis(), code, action_translated=advice
            )
            self.assertIn(advice, script)
            self.assertSpeakable(script, code)

    def test_english_action_cannot_reach_a_devanagari_voice(self):
        """Belt and braces: a caller passing raw English must not break the voice."""
        script = composer_service.compose_voice_script(
            _diagnosis(), "hi", action_translated="Spray Mancozeb now"
        )
        self.assertSpeakable(script, "hi")


class TextAdvisoryTest(unittest.TestCase):
    def test_every_language_renders_a_text_advisory(self):
        for code in ALL:
            text = composer_service.compose_text_advisory(_diagnosis(), code)
            self.assertIn(PHRASES[code]["labels"]["header"], text)
            self.assertIn("Early Blight", text, "the exact name must survive for the shop")

    def test_escalation_text_offers_no_treatment_in_any_language(self):
        for code in ALL:
            text = composer_service.compose_text_advisory(unavailable_diagnosis(), code)
            self.assertNotIn("₹", text, f"{code}: escalation showed a cost")
            self.assertNotIn("2g", text, f"{code}: escalation showed a dose")


class RenderingTest(unittest.TestCase):
    def test_dosage_renders_in_each_language(self):
        self.assertEqual(dosage_phrase("2g per litre", "mr"), "१ लिटर पाण्यात २ ग्रॅम")
        self.assertEqual(dosage_phrase("2g per litre", "hi"), "१ लीटर पानी में २ ग्राम")
        self.assertEqual(dosage_phrase("2g per litre", "bn"), "১ লিটার জলে ২ গ্রাম")
        # English drops the "1": "2 g per 1 litre" is not how anyone says it.
        self.assertEqual(dosage_phrase("2g per litre", "en"), "2 g per litre of water")

    def test_multi_litre_dose_keeps_its_quantity_in_every_language(self):
        self.assertEqual(dosage_phrase("10g per 5 litre", "mr"), "५ लिटर पाण्यात १० ग्रॅम")
        self.assertEqual(dosage_phrase("10g per 5 litre", "bn"), "৫ লিটার জলে ১০ গ্রাম")
        self.assertEqual(dosage_phrase("10g per 5 litre", "en"), "10 g per 5 litre of water")

    def test_unparseable_dosage_is_none_in_every_language(self):
        for code in ALL:
            self.assertIsNone(dosage_phrase("as per label", code))
            self.assertIsNone(dosage_phrase(None, code))

    def test_binomial_is_dropped_even_in_english(self):
        """An en-IN voice reads 'Alternaria solani' as gibberish too."""
        self.assertEqual(disease_name("Early Blight (Alternaria solani)", "en"), "Early Blight")

    def test_unmapped_disease_is_none_for_non_latin_but_passes_through_english(self):
        self.assertIsNone(disease_name("Some Unmapped Condition", "bn"))
        self.assertEqual(disease_name("Some Unmapped Condition", "en"), "Some Unmapped Condition")


class LanguageCommandTest(unittest.TestCase):
    def test_named_languages_are_recognised(self):
        for text, expected in [
            ("hindi", "hi"), ("Marathi", "mr"), ("english", "en"),
            ("bangla", "bn"), ("বাংলা", "bn"), ("हिंदी", "hi"), ("language: hindi", "hi"),
        ]:
            self.assertEqual(parse_language_command(text), expected, text)

    def test_a_note_that_merely_mentions_a_language_is_not_a_command(self):
        """Otherwise a farmer describing their crop silently changes settings."""
        for text in [
            "my hindi neighbour has the same spots",
            "the english variety of tomato",
            "spots on my leaves",
        ]:
            self.assertIsNone(parse_language_command(text), text)

    def test_bare_language_word_asks_for_the_menu(self):
        self.assertTrue(is_language_request("language"))
        self.assertTrue(is_language_request("भाषा"))
        self.assertFalse(is_language_request("language hindi"))


class ResolutionTest(unittest.TestCase):
    """pick > detect > region > default."""

    def setUp(self):
        pipeline.user_state_service.user_sessions.clear()

    def _passport(self, state):
        return mock.Mock(state=state)

    def test_explicit_choice_wins_over_everything(self):
        pipeline.user_state_service.set_user_language("p", "bn")
        pipeline.user_state_service.set_detected_language("p", "hi")
        code = run(pipeline.resolve_language("p", passport=self._passport("Maharashtra")))
        self.assertEqual(code, "bn")

    def test_detection_wins_over_region(self):
        pipeline.user_state_service.set_detected_language("p", "hi")
        code = run(pipeline.resolve_language("p", passport=self._passport("Maharashtra")))
        self.assertEqual(code, "hi")

    def test_region_decides_when_the_farmer_has_said_nothing(self):
        self.assertEqual(
            run(pipeline.resolve_language("p", passport=self._passport("West Bengal"))), "bn"
        )
        self.assertEqual(
            run(pipeline.resolve_language("p", passport=self._passport("Bihar"))), "hi"
        )

    def test_every_other_state_is_answered_in_hindi(self):
        """The rule: West Bengal -> bn, Maharashtra -> mr, everywhere else -> hi."""
        for state in ["Kerala", "Punjab", "Telangana", "Gujarat", "Goa", "Assam"]:
            self.assertEqual(
                run(pipeline.resolve_language("p", passport=self._passport(state))),
                "hi",
                f"{state} should be answered in Hindi",
            )

    def test_only_west_bengal_gets_bengali_and_only_maharashtra_marathi(self):
        self.assertEqual(
            run(pipeline.resolve_language("p", passport=self._passport("West Bengal"))), "bn"
        )
        self.assertEqual(
            run(pipeline.resolve_language("p", passport=self._passport("Maharashtra"))), "mr"
        )
        # Neighbours that share the language culturally are still Hindi here,
        # because the rule is by state and not by linguistics.
        self.assertEqual(
            run(pipeline.resolve_language("p", passport=self._passport("Goa"))), "hi"
        )

    def test_english_is_never_reached_by_location_alone(self):
        """English stays available by choice or detection, never by a pin."""
        for state in ["Kerala", "Tamil Nadu", "Nagaland"]:
            self.assertNotEqual(
                run(pipeline.resolve_language("p", passport=self._passport(state))), "en"
            )

    def test_default_when_there_is_no_signal_at_all(self):
        self.assertEqual(run(pipeline.resolve_language("p")), DEFAULT_LANGUAGE)

    def test_unavailable_passport_is_no_evidence_not_an_unmapped_state(self):
        """A ground outage must not silently switch every farmer to English."""
        from contracts.fallbacks import context_unavailable_passport

        passport = context_unavailable_passport(
            lat=19.9975, lon=73.7898, geohash="te7u23x", plot_id="hash_x"
        )
        self.assertEqual(
            run(pipeline.resolve_language("p", passport=passport)), DEFAULT_LANGUAGE
        )

    def test_bengali_note_is_detected_without_an_api_call(self):
        with mock.patch.object(
            pipeline.translate_service, "detect", new=mock.AsyncMock()
        ) as detect:
            code = run(pipeline.resolve_language("p", note="আমার গাছে দাগ পড়েছে"))
        self.assertEqual(code, "bn")
        detect.assert_not_awaited()

    def test_devanagari_note_asks_the_api_rather_than_guessing(self):
        """Hindi and Marathi share a script; picking one silently is a real error."""
        with mock.patch.object(
            pipeline.translate_service, "detect", new=mock.AsyncMock(return_value="hi")
        ) as detect:
            code = run(pipeline.resolve_language("p", note="मेरे पौधे पर धब्बे हैं"))
        detect.assert_awaited_once()
        self.assertEqual(code, "hi")

    def test_devanagari_note_falls_through_when_detection_is_unavailable(self):
        with mock.patch.object(
            pipeline.translate_service, "detect", new=mock.AsyncMock(return_value=None)
        ):
            code = run(pipeline.resolve_language(
                "p", note="मेरे पौधे पर धब्बे हैं", passport=self._passport("Bihar")
            ))
        self.assertEqual(code, "hi", "region should decide when detection cannot")

    def test_state_mapping_is_case_insensitive(self):
        self.assertEqual(language_for_state("west bengal"), "bn")
        self.assertEqual(language_for_state("WEST BENGAL"), "bn")
        self.assertEqual(language_for_state("maharashtra"), "mr")
        # None means "this table has nothing to say", and the caller then uses
        # FALLBACK_BY_REGION. It does not mean "unknown place".
        self.assertIsNone(language_for_state("Kerala"))
        self.assertIsNone(language_for_state(None))

    def test_script_detection_refuses_to_guess_between_hindi_and_marathi(self):
        self.assertIsNone(detect_from_text("मेरे पौधे पर धब्बे"))
        self.assertEqual(detect_from_text("আমার গাছে দাগ"), "bn")
        self.assertEqual(detect_from_text("spots on my plant"), "en")


if __name__ == "__main__":
    unittest.main()
