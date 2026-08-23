"""Unit test suite for DBSCAN epidemiological clustering and k-anonymity enforcement."""

import unittest
from datetime import datetime, timedelta, timezone

from ground.services.cluster import clustering_service

NOW = datetime.now(timezone.utc)


def _obs(prefix, i, lat, lon, disease, days_ago=2, geohash="te7u23x"):
    return {
        "plot_id": f"{prefix}_{i}",
        "geohash": geohash,
        "lat": lat,
        "lon": lon,
        "disease": disease,
        "created_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }


# 7 reports in one 5 km cell (hotspot) + 3 reports 20 km away (sub-threshold).
FIXTURE_OBSERVATIONS = [
    _obs("plot_nashik", i, 19.9975 + i * 0.001, 73.7898 + i * 0.001, "Early Blight")
    for i in range(7)
] + [
    _obs("plot_sub", i, 20.1500 + i * 0.001, 73.9000 + i * 0.001, "Early Blight", geohash="te7u90y")
    for i in range(3)
]


class TestDBSCANClustering(unittest.TestCase):
    def test_hotspot_cluster_formation(self):
        clusters = clustering_service.cluster_observations(FIXTURE_OBSERVATIONS)
        self.assertEqual(len(clusters), 1, "Seed data must yield exactly 1 hotspot cluster")

        hotspot = clusters[0]
        self.assertEqual(hotspot.disease, "Early Blight")
        self.assertGreaterEqual(hotspot.report_count, 5, "Cluster report count must be >= 5 for k-anonymity")
        self.assertGreaterEqual(hotspot.distinct_plots, 3, "Distinct plots must be >= 3")

    def test_sub_threshold_cluster_never_surfaces(self):
        """The 3-report group is the k-anonymity proof — it must not appear."""
        clusters = clustering_service.cluster_observations(FIXTURE_OBSERVATIONS)
        for c in clusters:
            self.assertGreaterEqual(c.report_count, 5)
        # The sub-threshold group sits ~17km north; no cluster centroid is near it.
        self.assertTrue(all(c.centroid[0] < 20.05 for c in clusters))

    def test_observations_outside_seven_day_window_are_excluded(self):
        """A stale report must not keep an outbreak alive, or its neighbours get warned about nothing."""
        stale = [
            _obs("plot_old", i, 19.9975 + i * 0.001, 73.7898 + i * 0.001, "Early Blight", days_ago=400)
            for i in range(7)
        ]
        self.assertEqual(clustering_service.cluster_observations(stale), [])

    def test_undated_observations_are_excluded(self):
        """An outbreak alert asserts 'right now' — an undated report cannot support that."""
        undated = [{k: v for k, v in o.items() if k != "created_at"} for o in FIXTURE_OBSERVATIONS]
        self.assertEqual(clustering_service.cluster_observations(undated), [])

    def test_diseases_are_clustered_separately(self):
        """Five different diseases in one cell is not an outbreak of anything."""
        mixed = [
            _obs("plot_mixed", i, 19.9975 + i * 0.001, 73.7898 + i * 0.001, d)
            for i, d in enumerate(["Early Blight", "Late Blight", "Purple Blotch",
                                   "Nitrogen Deficiency", "Bacterial Blight"])
        ]
        self.assertEqual(clustering_service.cluster_observations(mixed), [])

    def test_reported_radius_reflects_actual_extent(self):
        clusters = clustering_service.cluster_observations(FIXTURE_OBSERVATIONS)
        self.assertGreater(clusters[0].radius_km, 0.0)
        self.assertLess(clusters[0].radius_km, 5.0, "Cluster extent cannot exceed the 5km DBSCAN eps")

    def test_first_seen_is_the_earliest_report(self):
        """Drives 'how long has this been spreading' — must not reset to now on every sweep."""
        spread = [
            _obs("plot_time", i, 19.9975 + i * 0.001, 73.7898 + i * 0.001, "Early Blight", days_ago=d)
            for i, d in enumerate([6, 5, 4, 3, 2, 1, 1])
        ]
        clusters = clustering_service.cluster_observations(spread)
        self.assertEqual(len(clusters), 1)
        self.assertLess(clusters[0].first_seen, NOW - timedelta(days=5))


if __name__ == "__main__":
    unittest.main()
