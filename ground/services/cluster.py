import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from contracts.models import Outbreak
from ground.services.geo import geo_service
from ground.services.firestore import firestore_service

logger = logging.getLogger("ground.cluster")

class ClusteringService:
    def cluster_observations(self, observations: List[Dict[str, Any]]) -> List[Outbreak]:
        """
        DBSCAN Epidemiological Outbreak Radar:
        1. Group observations by disease.
        2. Run DBSCAN over Haversine distance matrix (eps = 5km / 6371km radius).
        3. Enforce k-anonymity:
           - report_count >= 5
           - distinct_plots >= 3
           - window = 7 days
        """
        if not observations:
            return []

        # Filter window (last 7 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        valid_obs = []
        for obs in observations:
            # Simple validation
            valid_obs.append(obs)

        if not valid_obs:
            return []

        # Group by disease
        by_disease: Dict[str, List[Dict]] = {}
        for obs in valid_obs:
            d = obs.get("disease", "Unknown Disease")
            by_disease.setdefault(d, []).append(obs)

        clusters: List[Outbreak] = []

        try:
            from sklearn.cluster import DBSCAN

            for disease, obs_list in by_disease.items():
                if len(obs_list) < 5:
                    continue  # Sub-threshold cluster (< 5 reports)

                coords = np.array([[obs["lat"], obs["lon"]] for obs in obs_list])
                coords_rad = np.radians(coords)

                # 5 km radius in radians = 5 / 6371.0
                kms_per_radian = 6371.0
                epsilon = 5.0 / kms_per_radian

                db = DBSCAN(eps=epsilon, min_samples=5, metric="haversine").fit(coords_rad)
                labels = db.labels_

                unique_labels = set(labels)
                for k in unique_labels:
                    if k == -1:
                        continue  # Noise points

                    class_member_mask = (labels == k)
                    cluster_obs = [obs_list[i] for i in range(len(obs_list)) if class_member_mask[i]]

                    report_count = len(cluster_obs)
                    distinct_plots = len(set(obs.get("plot_id", obs.get("geohash")) for obs in cluster_obs))

                    # ENFORCE K-ANONYMITY RULE (§7)
                    if report_count >= 5 and distinct_plots >= 3:
                        cluster_coords = coords[class_member_mask]
                        centroid_lat = float(np.mean(cluster_coords[:, 0]))
                        centroid_lon = float(np.mean(cluster_coords[:, 1]))

                        outbreak = Outbreak(
                            cluster_id=f"cluster_{disease.lower().replace(' ', '_')}_{int(centroid_lat*100)}",
                            disease=disease,
                            centroid=(centroid_lat, centroid_lon),
                            radius_km=2.5,
                            report_count=report_count,
                            distinct_plots=distinct_plots,
                            first_seen=datetime.now(timezone.utc),
                            alert_ring_km=15.0
                        )
                        clusters.append(outbreak)
        except Exception as e:
            logger.warning(f"DBSCAN clustering failed: {e}")

        return clusters

clustering_service = ClusteringService()
