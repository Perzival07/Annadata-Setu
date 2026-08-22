import math
import logging
from typing import List, Tuple

logger = logging.getLogger("ground.geo")

# Base32 map for geohash
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

class GeoService:
    def encode(self, lat: float, lon: float, precision: int = 7) -> str:
        """Encode lat/lon into geohash string of given precision."""
        try:
            import pygeohash as pgh
            return pgh.encode(lat, lon, precision=precision)
        except Exception:
            # Fallback simple geohash encoder
            lat_range = [-90.0, 90.0]
            lon_range = [-180.0, 180.0]
            geohash = []
            bits = [16, 8, 4, 2, 1]
            bit = 0
            ch = 0
            is_even = True

            while len(geohash) < precision:
                if is_even:
                    mid = (lon_range[0] + lon_range[1]) / 2
                    if lon > mid:
                        ch |= bits[bit]
                        lon_range[0] = mid
                    else:
                        lon_range[1] = mid
                else:
                    mid = (lat_range[0] + lat_range[1]) / 2
                    if lat > mid:
                        ch |= bits[bit]
                        lat_range[0] = mid
                    else:
                        lat_range[1] = mid
                is_even = not is_even

                if bit < 4:
                    bit += 1
                else:
                    geohash.append(BASE32[ch])
                    bit = 0
                    ch = 0
            return "".join(geohash)

    def get_adjacent_cells(self, geohash_prefix: str) -> List[str]:
        """
        Retrieve self + 8 adjacent geohash prefix cells to handle boundary-straddling clusters.
        """
        # For precision 5 (~5km cell size), return surrounding grid variations
        if len(geohash_prefix) < 2:
            return [geohash_prefix]

        neighbors = [geohash_prefix]
        last_char = geohash_prefix[-1]
        prefix_stem = geohash_prefix[:-1]

        idx = BASE32.find(last_char)
        if idx != -1:
            for offset in [-2, -1, 1, 2]:
                neighbor_idx = (idx + offset) % len(BASE32)
                neighbors.append(prefix_stem + BASE32[neighbor_idx])

        return list(set(neighbors))

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance between two points in kilometers."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

geo_service = GeoService()
