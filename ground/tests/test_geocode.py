"""Tests for reverse geocoding and the district it decides.

The district is not a label. It picks the NDVI fallback curve, the soil
fallback, the cropping-history prior, and it is the key the outbreak radar
groups by. The defect these guard against: `district: str = "Nashik"` as a
default argument, which labelled every unlocated plot in India as Nashik and
filed its observation in Nashik's cluster.
"""

import asyncio
import unittest
from unittest import mock

from ground.services import geocode as geocode_module
from ground.services.geocode import (
    SOURCE_LIVE,
    SOURCE_MOCK,
    GeocodePlace,
    GeocodeService,
    _component,
)
from ground.services.passport import DEFAULT_DISTRICT, PassportAggregatorService


def run(coro):
    return asyncio.run(coro)


def _ok(components):
    return {"status": "OK", "results": [{"address_components": components}]}


class ComponentParsingTest(unittest.TestCase):
    def test_district_suffix_is_stripped(self):
        """Google returns 'Pune District'; our tables are keyed on 'Pune'."""
        result = {"address_components": [
            {"long_name": "Pune District", "types": ["administrative_area_level_2"]},
        ]}
        self.assertEqual(_component(result, ("administrative_area_level_2",)), "Pune")

    def test_taluka_is_used_when_no_district_component(self):
        result = {"address_components": [
            {"long_name": "Sinnar", "types": ["administrative_area_level_3"]},
        ]}
        self.assertEqual(
            _component(result, ("administrative_area_level_2", "administrative_area_level_3")),
            "Sinnar",
        )

    def test_preference_order_is_honoured(self):
        result = {"address_components": [
            {"long_name": "Sinnar", "types": ["administrative_area_level_3"]},
            {"long_name": "Nashik", "types": ["administrative_area_level_2"]},
        ]}
        self.assertEqual(
            _component(result, ("administrative_area_level_2", "administrative_area_level_3")),
            "Nashik",
        )

    def test_absent_component_is_none(self):
        self.assertEqual(_component({"address_components": []}, ("x",)), None)


class ReverseGeocodeTest(unittest.TestCase):
    def setUp(self):
        self.svc = GeocodeService()

    def _with_response(self, payload):
        response = mock.Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        client = mock.AsyncMock()
        client.get.return_value = response
        ctx = mock.MagicMock()
        ctx.__aenter__.return_value = client
        return mock.patch.object(geocode_module.httpx, "AsyncClient", return_value=ctx)

    def test_unconfigured_returns_none_rather_than_guessing(self):
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", None):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))

    def test_resolves_district_and_state(self):
        payload = _ok([
            {"long_name": "Nagpur", "types": ["administrative_area_level_2"]},
            {"long_name": "Maharashtra", "types": ["administrative_area_level_1"]},
        ])
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), self._with_response(payload):
            place = run(self.svc.reverse(21.1, 79.0))
        self.assertEqual((place.district, place.state), ("Nagpur", "Maharashtra"))
        self.assertEqual(place.source, SOURCE_LIVE)

    def test_mock_mode_does_not_credit_the_api_it_never_called(self):
        """data_sources is the DPG audit trail — MOCK must not name a live API."""
        with mock.patch.object(geocode_module, "MOCK", True):
            place = run(self.svc.reverse(21.1, 79.0))
        self.assertEqual(place.source, SOURCE_MOCK)
        self.assertNotEqual(place.source, SOURCE_LIVE)

    def test_zero_results_returns_none(self):
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), \
             self._with_response({"status": "ZERO_RESULTS", "results": []}):
            self.assertIsNone(run(self.svc.reverse(0.0, 0.0)))

    def test_api_error_status_returns_none(self):
        payload = {"status": "REQUEST_DENIED", "error_message": "key not authorised"}
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), self._with_response(payload):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))

    def test_result_without_district_returns_none(self):
        """A state alone is not enough — everything downstream keys on district."""
        payload = _ok([{"long_name": "Maharashtra", "types": ["administrative_area_level_1"]}])
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), self._with_response(payload):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))

    def test_network_failure_returns_none(self):
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), \
             mock.patch.object(geocode_module.httpx, "AsyncClient", side_effect=OSError("no route")):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))


class PlaceResolutionTest(unittest.TestCase):
    """How the aggregator decides what to put in PlotPassport.district."""

    def setUp(self):
        self.agg = PassportAggregatorService()

    def test_caller_supplied_district_is_not_overridden(self):
        """The officer dashboard already knows its district; do not geocode over it."""
        with mock.patch(
            "ground.services.passport.geocode_service.reverse", new=mock.AsyncMock()
        ) as reverse:
            district, state, source = run(
                self.agg._resolve_place(21.1, 79.0, "Vidarbha", "Maharashtra")
            )
        reverse.assert_not_called()
        self.assertEqual(district, "Vidarbha")
        self.assertIsNone(source, "an asserted district was not looked up by anything")

    def test_pin_decides_when_no_district_supplied(self):
        with mock.patch(
            "ground.services.passport.geocode_service.reverse",
            new=mock.AsyncMock(return_value=GeocodePlace("Nagpur", "Maharashtra", SOURCE_LIVE)),
        ):
            district, state, source = run(self.agg._resolve_place(21.1, 79.0, None, None))
        self.assertEqual((district, state), ("Nagpur", "Maharashtra"))
        self.assertEqual(source, SOURCE_LIVE, "a looked-up district is recorded as provenance")

    def test_provenance_label_comes_from_whatever_resolved_it(self):
        """A mocked lookup must be credited to the fixture, not to Google."""
        with mock.patch(
            "ground.services.passport.geocode_service.reverse",
            new=mock.AsyncMock(return_value=GeocodePlace("Nashik", "Maharashtra", SOURCE_MOCK)),
        ):
            _d, _s, source = run(self.agg._resolve_place(21.1, 79.0, None, None))
        self.assertEqual(source, SOURCE_MOCK)

    def test_unresolvable_pin_falls_back_without_claiming_provenance(self):
        with mock.patch(
            "ground.services.passport.geocode_service.reverse",
            new=mock.AsyncMock(return_value=None),
        ):
            district, _state, source = run(self.agg._resolve_place(21.1, 79.0, None, None))
        self.assertEqual(district, DEFAULT_DISTRICT)
        self.assertIsNone(
            source, "a fallback district must not be attributed to the Geocoding API"
        )


if __name__ == "__main__":
    unittest.main()
