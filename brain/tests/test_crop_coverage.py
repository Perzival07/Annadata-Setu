"""Coverage across the crops this project claims to advise on.

The built-in notes, the CROPS constant and the per-language disease tables are
three lists that must agree, and nothing forces them to. A crop added to one and
forgotten in another fails quietly: retrieval returns an unrelated crop's notes,
or the voice note says "symptoms of disease" instead of naming what the farmer
has. Both look like the system working.
"""

import re
import unittest

from brain.services.rag import BUILTIN_KNOWLEDGE, RAGService
from contracts.constants import CROPS
from contracts.languages import LANGUAGES, get
from channel.services.phrasebook import DISEASE_NAMES
from channel.services.render import disease_name

CROPS_WITH_NOTES = sorted({entry["crop"] for entry in BUILTIN_KNOWLEDGE})
NON_LATIN = [c for c in LANGUAGES if get(c).script != "latin"]


def _builtin_only() -> RAGService:
    svc = RAGService.__new__(RAGService)
    svc.chroma_dir, svc.collection, svc.embedder_mismatch = "/nonexistent", None, None
    return svc


class CropCoverageTest(unittest.TestCase):
    def test_every_declared_crop_has_built_in_notes(self):
        """CROPS is what we tell the world we cover; notes are what we actually have."""
        missing = [c for c in CROPS if c not in CROPS_WITH_NOTES]
        self.assertEqual(missing, [], f"declared but no agronomic notes: {missing}")

    def test_retrieval_returns_the_right_crop(self):
        """A Rice query must not come back with Tomato notes."""
        svc = _builtin_only()
        for crop in CROPS_WITH_NOTES:
            docs = svc.retrieve_context(crop, "disease symptoms management")
            self.assertTrue(docs, f"{crop} retrieved nothing")
            for doc in docs:
                self.assertIn(
                    crop.lower(), doc["content"].lower(),
                    f"{crop} query returned a note that never mentions it",
                )

    def test_built_in_notes_stay_uncitable(self):
        """Adding crops must not smuggle in a citable source. See test_rag.py."""
        svc = _builtin_only()
        for crop in CROPS_WITH_NOTES:
            for doc in svc.retrieve_context(crop, "management"):
                self.assertIsNone(doc["source"])
                self.assertEqual(doc["provenance"], "builtin")

    def test_no_note_claims_a_document_filename(self):
        blob = " ".join(e["content"] for e in BUILTIN_KNOWLEDGE)
        self.assertNotIn(".pdf", blob, "a built-in note must not name a document")

    def test_notes_are_detailed_enough_to_be_worth_retrieving(self):
        for entry in BUILTIN_KNOWLEDGE:
            self.assertGreater(
                len(entry["content"]), 180,
                f"{entry['crop']}/{entry['disease']} is too thin to help a diagnosis",
            )


class DiseaseNamingTest(unittest.TestCase):
    """Every disease we describe must be speakable in every language."""

    def test_every_built_in_disease_has_a_name_in_every_language(self):
        for entry in BUILTIN_KNOWLEDGE:
            for code in NON_LATIN:
                rendered = disease_name(entry["disease"], code)
                self.assertIsNotNone(
                    rendered,
                    f"{entry['disease']!r} has no {code} name — the voice note would "
                    f"fall back to 'symptoms of disease' and never name it",
                )

    def test_names_as_they_appear_in_the_notes_also_resolve(self):
        """The model echoes the note's own phrasing, binomial and all."""
        for entry in BUILTIN_KNOWLEDGE:
            as_written = entry["content"].split(" in ")[0]
            for code in NON_LATIN:
                self.assertIsNotNone(
                    disease_name(as_written, code),
                    f"{as_written!r} does not resolve in {code}",
                )

    def test_disease_names_use_their_own_script(self):
        from contracts.languages import has_foreign_script

        for code in NON_LATIN:
            for key, value in DISEASE_NAMES[code].items():
                self.assertFalse(
                    has_foreign_script(value, code),
                    f"{code} name for {key!r} contains script its voice cannot read: {value!r}",
                )

    def test_generic_names_do_not_shadow_specific_ones(self):
        """'rust' must not swallow 'yellow rust' — specific keys win."""
        for code in NON_LATIN:
            self.assertNotEqual(
                disease_name("Yellow Rust", code), disease_name("Rust", code)
            )
            self.assertNotEqual(
                disease_name("White Rust", code), disease_name("Rust", code)
            )

    def test_an_unlisted_variant_still_falls_back_to_the_generic(self):
        """Substring matching is what makes a table of 37 cover more than 37."""
        for code in NON_LATIN:
            self.assertEqual(disease_name("Stripe Rust", code), disease_name("Rust", code))
            self.assertIsNotNone(disease_name("Sugarcane Wilt", code))


if __name__ == "__main__":
    unittest.main()
