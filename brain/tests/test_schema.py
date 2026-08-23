"""Conformance tests for the published DPG schemas.

These guard two things that are easy to break silently:
  1. the schemas stay in step with the frozen contract in contracts/models.py
  2. the JSON-LD actually resolves — an unmapped term is dropped by expansion
     rather than raising, so a broken context looks fine until someone consumes it
"""

import json
import os
import unittest

from contracts.models import PlotPassport, Diagnosis, Outbreak
from brain.services.registry import MODEL_REGISTRY

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "schema")
NS = "https://perzival07.github.io/Annadata-Setu/ns/v1#"


def _load(name):
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _properties_of(doc, class_local):
    return {
        node["label"]
        for node in doc["@graph"]
        if node.get("@type") == "rdf:Property" and node.get("domain") == f"as:{class_local}"
    }


class SchemaParityTest(unittest.TestCase):
    """Every frozen contract field must be described, and nothing extra invented."""

    def _assert_parity(self, fields, filename, class_local):
        described = _properties_of(_load(filename), class_local)
        self.assertEqual(
            set(fields), described,
            f"{filename}#{class_local} has drifted from the contract:\n"
            f"  missing from schema: {sorted(set(fields) - described)}\n"
            f"  not in contract:     {sorted(described - set(fields))}",
        )

    def test_plot_passport(self):
        self._assert_parity(PlotPassport.model_fields, "plot-passport.v1.jsonld", "PlotPassport")

    def test_advisory_event(self):
        self._assert_parity(Diagnosis.model_fields, "advisory-event.v1.jsonld", "AdvisoryEvent")

    def test_outbreak(self):
        self._assert_parity(Outbreak.model_fields, "disease-observation.v1.jsonld", "Outbreak")

    def test_disease_observation(self):
        from ground.routers.observations import ObservationCreateRequest
        fields = set(ObservationCreateRequest.model_fields) | {"obs_id", "created_at"}
        self._assert_parity(fields, "disease-observation.v1.jsonld", "DiseaseObservation")

    def test_model_registry(self):
        self._assert_parity(MODEL_REGISTRY[0].keys(), "model-registry.v1.jsonld", "ModelRegistryEntry")


class SchemaDocumentTest(unittest.TestCase):
    FILES = [
        "plot-passport.v1.jsonld",
        "advisory-event.v1.jsonld",
        "disease-observation.v1.jsonld",
        "model-registry.v1.jsonld",
    ]

    def test_every_term_uses_the_project_namespace_or_a_standard_one(self):
        """Terms must resolve somewhere real — schema.org has no PlotPassport."""
        allowed = ("as:", "geo:", "dcterms:", "rdf:", "rdfs:", "xsd:", "owl:")
        for name in self.FILES:
            doc = _load(name)
            self.assertEqual(doc["@context"]["as"], NS, f"{name}: wrong namespace")
            for node in doc["@graph"]:
                with self.subTest(schema=name, node=node["@id"]):
                    self.assertTrue(
                        node["@id"].startswith(allowed),
                        f"{node['@id']} is not in a declared prefix",
                    )

    def test_documents_expand_without_dropping_terms(self):
        try:
            from pyld import jsonld
        except ImportError:
            self.skipTest("pyld not installed")
        for name in self.FILES:
            doc = _load(name)
            with self.subTest(schema=name):
                expanded = jsonld.expand(doc)
                self.assertTrue(expanded, f"{name} expanded to nothing")
                self.assertEqual(
                    len(expanded[0].get("@graph", [])), len(doc["@graph"]),
                    f"{name}: a term failed to resolve and was silently dropped",
                )

    def test_conformance_constraints_are_published(self):
        """The k-anonymity floor and the escalation threshold are part of the standard."""
        obs = json.dumps(_load("disease-observation.v1.jsonld"))
        self.assertIn("report_count >= 5", obs)
        self.assertIn("distinct_plots >= 3", obs)
        adv = json.dumps(_load("advisory-event.v1.jsonld"))
        self.assertIn("confidence < 0.65", adv)

    def test_sample_dataset_is_populated(self):
        sample = _load("sample-dataset.json")
        types = [n["@type"] for n in sample["@graph"]]
        for expected in ["PlotPassport", "AdvisoryEvent", "DiseaseObservation",
                         "Outbreak", "ModelRegistryEntry"]:
            self.assertIn(expected, types, f"sample dataset has no {expected} record")
        # One advisory must demonstrate the escalation path, dosage stripped.
        escalated = [n for n in sample["@graph"]
                     if n["@type"] == "AdvisoryEvent" and n.get("escalate_to_human")]
        self.assertTrue(escalated, "sample dataset never shows the escalation outcome")
        self.assertIsNone(escalated[0]["dosage"])
        self.assertEqual(escalated[0]["estimated_cost_inr"], 0)


if __name__ == "__main__":
    unittest.main()
