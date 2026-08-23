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
    SOURCE_GOOGLE,
    SOURCE_MOCK,
    SOURCE_NOMINATIM,
    GeocodePlace,
    GeocodeService,
    _component,
    active_provider,
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

    def test_no_key_falls_back_to_nominatim_rather_than_giving_up(self):
        """The whole point: a clone with no credentials still resolves districts.

        Before, an unset key meant every plot was labelled Nashik — including
        its telemetry fallbacks, its outbreak cluster and, since multi-language,
        the language the farmer is answered in.
        """
        payload = {"address": {"state_district": "Nagpur", "state": "Maharashtra"}}
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", None), \
             mock.patch.object(geocode_module, "GEOCODER", ""), self._with_response(payload):
            place = run(self.svc.reverse(21.1, 79.0))
        self.assertEqual((place.district, place.state), ("Nagpur", "Maharashtra"))
        self.assertEqual(place.source, SOURCE_NOMINATIM)

    def test_geocoding_can_be_switched_off_entirely(self):
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "GEOCODER", "none"):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))

    def test_a_key_upgrades_to_google_automatically(self):
        with mock.patch.object(geocode_module, "API_KEY", "k"), \
             mock.patch.object(geocode_module, "GEOCODER", ""):
            self.assertEqual(active_provider(), "google")
        with mock.patch.object(geocode_module, "API_KEY", None), \
             mock.patch.object(geocode_module, "GEOCODER", ""):
            self.assertEqual(active_provider(), "nominatim")

    def test_forcing_google_without_a_key_disables_rather_than_silently_using_osm(self):
        """An operator who asked for Google should not get a different provider."""
        with mock.patch.object(geocode_module, "API_KEY", None), \
             mock.patch.object(geocode_module, "GEOCODER", "google"):
            self.assertIsNone(active_provider())

    def test_nominatim_result_without_a_district_returns_none(self):
        payload = {"address": {"state": "Maharashtra"}}
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "GEOCODER", "nominatim"), self._with_response(payload):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))

    def test_nominatim_error_payload_returns_none(self):
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "GEOCODER", "nominatim"), \
             self._with_response({"error": "Unable to geocode"}):
            self.assertIsNone(run(self.svc.reverse(0.0, 0.0)))

    def test_nominatim_falls_back_to_county_when_there_is_no_state_district(self):
        payload = {"address": {"county": "Sinnar", "state": "Maharashtra"}}
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "GEOCODER", "nominatim"), self._with_response(payload):
            self.assertEqual(run(self.svc.reverse(19.8, 74.0)).district, "Sinnar")

    def test_resolves_district_and_state(self):
        payload = _ok([
            {"long_name": "Nagpur", "types": ["administrative_area_level_2"]},
            {"long_name": "Maharashtra", "types": ["administrative_area_level_1"]},
        ])
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), \
             mock.patch.object(geocode_module, "GEOCODER", "google"), self._with_response(payload):
            place = run(self.svc.reverse(21.1, 79.0))
        self.assertEqual((place.district, place.state), ("Nagpur", "Maharashtra"))
        self.assertEqual(place.source, SOURCE_GOOGLE)

    def test_mock_mode_does_not_credit_the_api_it_never_called(self):
        """data_sources is the DPG audit trail — MOCK must not name a live API."""
        with mock.patch.object(geocode_module, "MOCK", True):
            place = run(self.svc.reverse(21.1, 79.0))
        self.assertEqual(place.source, SOURCE_MOCK)
        self.assertNotEqual(place.source, SOURCE_GOOGLE)

    def test_zero_results_returns_none(self):
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), \
             mock.patch.object(geocode_module, "GEOCODER", "google"), \
             self._with_response({"status": "ZERO_RESULTS", "results": []}):
            self.assertIsNone(run(self.svc.reverse(0.0, 0.0)))

    def test_api_error_status_returns_none(self):
        payload = {"status": "REQUEST_DENIED", "error_message": "key not authorised"}
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), \
             mock.patch.object(geocode_module, "GEOCODER", "google"), self._with_response(payload):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))

    def test_result_without_district_returns_none(self):
        """A state alone is not enough — everything downstream keys on district."""
        payload = _ok([{"long_name": "Maharashtra", "types": ["administrative_area_level_1"]}])
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), \
             mock.patch.object(geocode_module, "GEOCODER", "google"), self._with_response(payload):
            self.assertIsNone(run(self.svc.reverse(21.1, 79.0)))

    def test_network_failure_returns_none(self):
        with mock.patch.object(geocode_module, "MOCK", False), \
             mock.patch.object(geocode_module, "API_KEY", "k"), \
             mock.patch.object(geocode_module, "GEOCODER", "google"), \
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
            new=mock.AsyncMock(return_value=GeocodePlace("Nagpur", "Maharashtra", SOURCE_GOOGLE)),
        ):
            district, state, source = run(self.agg._resolve_place(21.1, 79.0, None, None))
        self.assertEqual((district, state), ("Nagpur", "Maharashtra"))
        self.assertEqual(source, SOURCE_GOOGLE, "a looked-up district is recorded as provenance")

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


class PlaceEndpointTest(unittest.TestCase):
    """GET /place — the lookup the web app's location capture calls.

    It exists so the page can name the district a captured GPS fix landed in
    before the farmer commits to a diagnosis. Going through /plot-passport for
    that would run Earth Engine, SoilGrids and a weather forecast to answer a
    question none of them are involved in.
    """

    def setUp(self):
        from fastapi.testclient import TestClient
        from ground.main import app

        self.client = TestClient(app)

    def _get(self, lat, lon):
        return self.client.get(f"/place?lat={lat}&lon={lon}").json()

    def test_resolved_pin_returns_district_state_and_provenance(self):
        place = GeocodePlace("Bankura", "West Bengal", SOURCE_NOMINATIM)
        with mock.patch(
            "ground.routers.passport.geocode_service.reverse",
            new=mock.AsyncMock(return_value=place),
        ):
            body = self._get(23.2324, 87.069)
        self.assertTrue(body["resolved"])
        self.assertEqual((body["district"], body["state"]), ("Bankura", "West Bengal"))
        self.assertEqual(body["source"], SOURCE_NOMINATIM)

    def test_unresolvable_pin_says_so_rather_than_guessing(self):
        """Offshore, or geocoding down. The caller must not show a guess."""
        with mock.patch(
            "ground.routers.passport.geocode_service.reverse",
            new=mock.AsyncMock(return_value=None),
        ):
            body = self._get(0.0, 0.0)
        self.assertFalse(body["resolved"])
        self.assertIsNone(body["district"])
        self.assertIsNone(body["state"])

    def test_it_does_not_build_a_passport(self):
        """The whole point is that it is cheap — no telemetry may be fetched."""
        with mock.patch(
            "ground.routers.passport.geocode_service.reverse",
            new=mock.AsyncMock(return_value=GeocodePlace("Nashik", "Maharashtra", SOURCE_MOCK)),
        ), mock.patch(
            "ground.routers.passport.passport_aggregator_service.build_plot_passport",
            new=mock.AsyncMock(),
        ) as build:
            self._get(19.9975, 73.7898)
        build.assert_not_called()
