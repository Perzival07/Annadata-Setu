"""Unit test suite for DBSCAN epidemiological clustering and k-anonymity enforcement."""

import unittest
from ground.services.cluster import clustering_service

# Fixture observation data: 7 reports in 1 cell (hotspot) + 3 reports in another (sub-threshold)
FIXTURE_OBSERVATIONS = [
    {"plot_id": f"plot_nashik_{i}", "geohash": "te7u23x", "lat": 19.9975 + (i*0.001), "lon": 73.7898 + (i*0.001), "disease": "Early Blight"}
    for i in range(7)
] + [
    {"plot_id": f"plot_sub_{i}", "geohash": "te7u90y", "lat": 20.1500 + (i*0.001), "lon": 73.9000 + (i*0.001), "disease": "Early Blight"}
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
        print(f"Cluster Test Passed: Cluster {hotspot.cluster_id} formed with {hotspot.report_count} reports!")

if __name__ == "__main__":
    unittest.main()
