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

    def decode_bbox(self, geohash: str) -> Tuple[float, float, float, float]:
        """Decode a geohash into its bounding box (lat_min, lat_max, lon_min, lon_max)."""
        lat_range = [-90.0, 90.0]
        lon_range = [-180.0, 180.0]
        is_even = True
        for ch in geohash:
            idx = BASE32.find(ch)
            if idx == -1:
                break
            for mask in (16, 8, 4, 2, 1):
                if is_even:
                    mid = (lon_range[0] + lon_range[1]) / 2
                    if idx & mask:
                        lon_range[0] = mid
                    else:
                        lon_range[1] = mid
                else:
                    mid = (lat_range[0] + lat_range[1]) / 2
                    if idx & mask:
                        lat_range[0] = mid
                    else:
                        lat_range[1] = mid
                is_even = not is_even
        return (lat_range[0], lat_range[1], lon_range[0], lon_range[1])

    def get_adjacent_cells(self, geohash_prefix: str) -> List[str]:
        """Self + the 8 true geohash neighbours, so a cluster straddling a cell
        boundary is not missed (BRAIN.md §11, 12:00).

        Geohash adjacency is not arithmetic on the last character. Base32 walks a
        Z-order curve, so the cell east of `tes3z` is `tes9b` — a different stem
        entirely — while `tes30` and `tes31`, which nudging the last character
        produces, sit nowhere near it. Stepping one cell width in real coordinates
        and re-encoding gets the actual neighbours at any precision.
        """
        if not geohash_prefix:
            return []

        precision = len(geohash_prefix)
        lat_min, lat_max, lon_min, lon_max = self.decode_bbox(geohash_prefix)
        lat_c = (lat_min + lat_max) / 2
        lon_c = (lon_min + lon_max) / 2
        lat_step = lat_max - lat_min
        lon_step = lon_max - lon_min

        neighbours = set()
        for dlat in (-1, 0, 1):
            for dlon in (-1, 0, 1):
                lat = max(-90.0, min(90.0, lat_c + dlat * lat_step))
                lon = lon_c + dlon * lon_step
                # Wrap across the antimeridian rather than clamping.
                lon = ((lon + 180.0) % 360.0) - 180.0
                neighbours.add(self.encode(lat, lon, precision))

        return sorted(neighbours)

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance between two points in kilometers."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

geo_service = GeoService()
