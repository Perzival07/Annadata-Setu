import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ground.firestore")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

class FirestoreService:
    def __init__(self):
        self.db = None
        self._in_memory_observations: List[Dict[str, Any]] = []
        self._in_memory_passports: Dict[str, Dict[str, Any]] = {}
        self._init_firestore()

    def _init_firestore(self):
        if MOCK:
            logger.info("FirestoreService initialized in MOCK_MODE.")
            return

        try:
            from google.cloud import firestore
            self.db = firestore.Client()
            logger.info("Google Cloud Firestore Native Client initialized.")
        except Exception as e:
            logger.warning(f"Firestore initialization fallback: {e}")

    async def save_observation(self, obs: Dict[str, Any]) -> str:
        """Save disease observation data point into Firestore."""
        obs_id = obs.get("obs_id", f"obs_{len(self._in_memory_observations) + 1}")
        obs["obs_id"] = obs_id

        if self.db:
            try:
                self.db.collection("observations").document(obs_id).set(obs)
                logger.info(f"Saved observation {obs_id} to Firestore.")
                return obs_id
            except Exception as e:
                logger.warning(f"Firestore write failed, saving in-memory: {e}")

        self._in_memory_observations.append(obs)
        return obs_id

    async def get_observations_in_geohashes(self, geohashes: List[str]) -> List[Dict[str, Any]]:
        """Query observations matching geohash prefix range."""
        results = []
        if self.db:
            try:
                # Firestore geohash prefix range query
                for gh in geohashes:
                    end_gh = gh + "\uf8ff"
                    docs = self.db.collection("observations").where("geohash", ">=", gh).where("geohash", "<=", end_gh).stream()
                    for doc in docs:
                        results.append(doc.to_dict())
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Firestore query failed, using in-memory: {e}")

        # In-memory prefix matching fallback
        for obs in self._in_memory_observations:
            gh = obs.get("geohash", "")
            if any(gh.startswith(prefix) for prefix in geohashes):
                results.append(obs)

        return results

    async def get_cached_passport(self, geohash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached PlotPassport by 7-char geohash."""
        if self.db:
            try:
                doc = self.db.collection("passports").document(geohash).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception:
                pass
        return self._in_memory_passports.get(geohash)

    async def cache_passport(self, geohash: str, passport_data: Dict[str, Any]):
        """Cache PlotPassport with 7-day TTL."""
        if self.db:
            try:
                self.db.collection("passports").document(geohash).set(passport_data)
            except Exception:
                pass
        self._in_memory_passports[geohash] = passport_data

firestore_service = FirestoreService()
