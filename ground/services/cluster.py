import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from contracts.models import Outbreak
from contracts.constants import (
    OUTBREAK_MIN_REPORTS,
    OUTBREAK_MIN_DISTINCT_PLOTS,
    OUTBREAK_WINDOW_DAYS,
    ALERT_RING_KM,
)
from ground.services.geo import geo_service
from ground.services.firestore import firestore_service

logger = logging.getLogger("ground.cluster")

# Undated observations are dropped rather than assumed current: an
# outbreak alert asserts "right now, near you", and we cannot assert that
# about a report with no timestamp.

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

        # Filter to the 7-day window. This cutoff used to be computed and then
        # ignored, so a report from last season still counted toward a live
        # outbreak — and toward the pre-emptive alerts sent to its neighbours.
        cutoff = datetime.now(timezone.utc) - timedelta(days=OUTBREAK_WINDOW_DAYS)
        valid_obs = [obs for obs in observations if self._is_within_window(obs, cutoff)]

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
                if len(obs_list) < OUTBREAK_MIN_REPORTS:
                    continue  # Sub-threshold cluster

                coords = np.array([[obs["lat"], obs["lon"]] for obs in obs_list])
                coords_rad = np.radians(coords)

                # 5 km radius in radians = 5 / 6371.0
                kms_per_radian = 6371.0
                epsilon = 5.0 / kms_per_radian

                db = DBSCAN(eps=epsilon, min_samples=OUTBREAK_MIN_REPORTS, metric="haversine").fit(coords_rad)
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
                    if report_count >= OUTBREAK_MIN_REPORTS and distinct_plots >= OUTBREAK_MIN_DISTINCT_PLOTS:
                        cluster_coords = coords[class_member_mask]
                        centroid_lat = float(np.mean(cluster_coords[:, 0]))
                        centroid_lon = float(np.mean(cluster_coords[:, 1]))

                        outbreak = Outbreak(
                            cluster_id=self._cluster_id(disease, centroid_lat, centroid_lon),
                            disease=disease,
                            centroid=(centroid_lat, centroid_lon),
                            radius_km=self._radius_km(centroid_lat, centroid_lon, cluster_obs),
                            report_count=report_count,
                            distinct_plots=distinct_plots,
                            first_seen=self._earliest_seen(cluster_obs),
                            alert_ring_km=ALERT_RING_KM
                        )
                        clusters.append(outbreak)
        except Exception as e:
            logger.warning(f"DBSCAN clustering failed: {e}")

        return clusters

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _is_within_window(obs: Dict[str, Any], cutoff: datetime) -> bool:
        raw = obs.get("created_at") or obs.get("timestamp")
        if not raw:
            return False
        if isinstance(raw, datetime):
            ts = raw
        else:
            try:
                ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                logger.warning(f"Unparseable observation timestamp {raw!r} — excluded from clustering.")
                return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts >= cutoff

    @staticmethod
    def _earliest_seen(cluster_obs: List[Dict[str, Any]]) -> datetime:
        """When this outbreak actually started — the field drives 'how long has this been spreading'."""
        stamps = []
        for obs in cluster_obs:
            raw = obs.get("created_at") or obs.get("timestamp")
            if not raw:
                continue
            try:
                ts = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            stamps.append(ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts)
        return min(stamps) if stamps else datetime.now(timezone.utc)

    @staticmethod
    def _radius_km(centroid_lat: float, centroid_lon: float, cluster_obs: List[Dict[str, Any]]) -> float:
        """Actual extent of the cluster, not a hardcoded 2.5 km."""
        distances = [
            geo_service.haversine_distance(centroid_lat, centroid_lon, obs["lat"], obs["lon"])
            for obs in cluster_obs
        ]
        return round(max(distances), 2) if distances else 0.0

    @staticmethod
    def _cluster_id(disease: str, lat: float, lon: float) -> str:
        """Stable across sweeps, and distinct for two clusters on the same latitude."""
        slug = disease.lower().replace(" ", "_")
        return f"cluster_{slug}_{int(round(lat * 1000))}_{int(round(lon * 1000))}"


clustering_service = ClusteringService()
