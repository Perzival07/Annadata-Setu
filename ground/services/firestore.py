import os
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ground.firestore")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
# Local compose runs have no GCP credentials. Setting this pins the datastore to
# the in-process store instead of waiting on a credential lookup that will fail.
FORCE_LOCAL_DB = os.getenv("FORCE_LOCAL_DB", "false").lower() == "true"

# BRAIN.md §11 (14:00): cache the passport by geohash for 7 days. The second
# demo run then drops 12s to 2s.
PASSPORT_TTL_DAYS = 7
# Clustering only ever looks at a 7-day window, so reading more is wasted I/O.
OBSERVATION_WINDOW_DAYS = 7


class FirestoreService:
    def __init__(self):
        self.db = None
        self._in_memory_observations: List[Dict[str, Any]] = []
        self._in_memory_passports: Dict[str, Dict[str, Any]] = {}
        self._init_firestore()

    def _init_firestore(self):
        if MOCK or FORCE_LOCAL_DB:
            logger.info("FirestoreService using the local in-process store (MOCK_MODE/FORCE_LOCAL_DB).")
            self._load_seed_observations()
            return

        try:
            from google.cloud import firestore
            self.db = firestore.Client()
            logger.info("Google Cloud Firestore Native Client initialized.")
        except Exception as e:
            logger.warning(f"Firestore initialization fallback: {e}")
            self._load_seed_observations()

    def _load_seed_observations(self):
        """Prime the local store from seed/observations.json.

        Without this the local store starts empty, so /outbreaks returns nothing
        and the radar cannot be demonstrated at all off Firestore. The seed ships
        in the image for exactly this reason (BRAIN.md §14).
        """
        path = os.path.join("seed", "observations.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                seeded = json.load(f)
            self._in_memory_observations.extend(seeded)
            logger.info(f"Primed local store with {len(seeded)} seed observations.")
        except Exception as e:
            logger.warning(f"Could not load seed observations: {e}")

    # ------------------------------------------------------------------ writes

    async def save_observation(self, obs: Dict[str, Any]) -> str:
        """Save a disease observation data point.

        The id must be unique per observation. Deriving it from the length of
        the in-memory list produced "obs_1" for every single write once the
        Firestore client was live (that list stays empty on the Firestore path),
        so all observations overwrote one document and no cluster could ever
        reach the k>=5 threshold.
        """
        obs_id = obs.get("obs_id") or f"obs_{uuid.uuid4().hex[:16]}"
        obs["obs_id"] = obs_id
        obs.setdefault("created_at", datetime.now(timezone.utc).isoformat())

        if self.db:
            try:
                self.db.collection("observations").document(obs_id).set(obs)
                logger.info(f"Saved observation {obs_id} to Firestore.")
                return obs_id
            except Exception as e:
                logger.warning(f"Firestore write failed, saving in-memory: {e}")

        self._in_memory_observations.append(obs)
        return obs_id

    async def cache_passport(self, geohash: str, passport_data: Dict[str, Any]):
        """Cache a PlotPassport under its 7-char geohash with a 7-day TTL."""
        record = dict(passport_data)
        record["cached_at"] = datetime.now(timezone.utc).isoformat()

        if self.db:
            try:
                self.db.collection("passports").document(geohash).set(record)
            except Exception as e:
                logger.warning(f"Passport cache write failed for {geohash}: {e}")
        self._in_memory_passports[geohash] = record

    # ------------------------------------------------------------------- reads

    async def get_observations_in_geohashes(self, geohashes: List[str]) -> List[Dict[str, Any]]:
        """Query observations whose geohash starts with any of the given prefixes."""
        results: List[Dict[str, Any]] = []
        seen: set = set()

        if self.db:
            try:
                for gh in geohashes:
                    # Firestore has no radius query; a prefix range is the
                    # documented substitute (BRAIN.md §11, 12:00).
                    end_gh = gh + "\uf8ff"
                    docs = (
                        self.db.collection("observations")
                        .where("geohash", ">=", gh)
                        .where("geohash", "<=", end_gh)
                        .stream()
                    )
                    for doc in docs:
                        d = doc.to_dict()
                        # Prefix ranges overlap, so the same document can come
                        # back for several cells. Counting it twice would inflate
                        # report_count straight through the k-anonymity gate.
                        if d.get("obs_id") in seen:
                            continue
                        seen.add(d.get("obs_id"))
                        results.append(d)
                return results
            except Exception as e:
                logger.warning(f"Firestore query failed, using in-memory: {e}")

        for obs in self._in_memory_observations:
            gh = obs.get("geohash", "")
            if any(gh.startswith(prefix) for prefix in geohashes) and obs.get("obs_id") not in seen:
                seen.add(obs.get("obs_id"))
                results.append(obs)

        return results

    async def get_all_observations(self) -> List[Dict[str, Any]]:
        """Every observation inside the clustering window, across all districts.

        Used by the scheduled radar sweep, which must not be scoped to a
        hardcoded set of geohash prefixes — that silently excluded any district
        outside the ones someone happened to type.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=OBSERVATION_WINDOW_DAYS)).isoformat()

        if self.db:
            try:
                docs = (
                    self.db.collection("observations")
                    .where("created_at", ">=", cutoff)
                    .stream()
                )
                return [doc.to_dict() for doc in docs]
            except Exception as e:
                logger.warning(f"Firestore full scan failed, using in-memory: {e}")

        return list(self._in_memory_observations)

    async def get_registered_plots(self) -> List[Dict[str, Any]]:
        """Every plot we can reach — the population the alert ring is drawn from.

        Falls back to the seeded roster, which ships inside the image precisely
        so the ring fan-out still demonstrates on a cold, credential-less run.
        """
        if self.db:
            try:
                docs = self.db.collection("plots").stream()
                plots = [doc.to_dict() for doc in docs]
                if plots:
                    return plots
            except Exception as e:
                logger.warning(f"Firestore plots read failed, using seed roster: {e}")

        return self._load_seed_plots()

    @staticmethod
    def _load_seed_plots() -> List[Dict[str, Any]]:
        path = os.path.join("seed", "plots.json")
        if not os.path.exists(path):
            logger.warning(f"No seed plot roster at {path}; alert ring will be empty.")
            return []
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read seed plot roster: {e}")
            return []

    async def get_cached_passport(self, geohash: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached PlotPassport, honouring the 7-day TTL."""
        record = None
        if self.db:
            try:
                doc = self.db.collection("passports").document(geohash).get()
                if doc.exists:
                    record = doc.to_dict()
            except Exception as e:
                logger.warning(f"Passport cache read failed for {geohash}: {e}")
        if record is None:
            record = self._in_memory_passports.get(geohash)
        if record is None:
            return None

        if self._is_expired(record):
            logger.info(f"Passport cache entry for {geohash} is older than {PASSPORT_TTL_DAYS}d — refetching.")
            return None

        # `cached_at` is bookkeeping, not part of the frozen PlotPassport model.
        return {k: v for k, v in record.items() if k != "cached_at"}

    @staticmethod
    def _is_expired(record: Dict[str, Any]) -> bool:
        cached_at = record.get("cached_at")
        if not cached_at:
            # Written before TTL tracking existed — treat as stale rather than
            # serving three-year-old NDVI as current.
            return True
        try:
            ts = datetime.fromisoformat(cached_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return True
        return datetime.now(timezone.utc) - ts > timedelta(days=PASSPORT_TTL_DAYS)


firestore_service = FirestoreService()
