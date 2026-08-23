import asyncio
import logging
import os
from typing import Any, Dict, List

import httpx

logger = logging.getLogger("functions.outbreak_radar")

CHANNEL_URL = os.getenv("CHANNEL_URL", "http://localhost:8001")
GROUND_URL = os.getenv("GROUND_URL", "http://localhost:8003")

ALERT_RING_KM = float(os.getenv("ALERT_RING_KM", "15.0"))
# Farmers inside the cluster already have the disease. A pre-emptive "act
# before it reaches you" is the wrong message for them.
EXCLUDE_WITHIN_KM = float(os.getenv("EXCLUDE_WITHIN_KM", "2.0"))


async def _fetch_ring(client: httpx.AsyncClient, centroid: List[float]) -> Dict[str, Any]:
    """Ask ground which plots sit in this cluster's alert ring."""
    res = await client.get(
        f"{GROUND_URL}/alert-ring",
        params={
            "lat": centroid[0],
            "lon": centroid[1],
            "radius_km": ALERT_RING_KM,
            "exclude_within_km": EXCLUDE_WITHIN_KM,
        },
    )
    res.raise_for_status()
    return res.json()


async def run_outbreak_radar():
    """
    Cloud Function Gen2 scheduled worker (cron: */30 * * * *):
    1. Query active outbreaks from ground.
    2. For each cluster, resolve the real 15 km ring of plots from ground.
    3. Push a pre-emptive warning to those farmers via channel.

    The ring lookup used to be skipped entirely: every cluster fanned out to the
    same three hardcoded phone numbers in a hardcoded district, which is both
    the wrong recipients and the wrong message.
    """
    logger.info("Executing scheduled Outbreak Radar sweep...")
    dispatched = 0

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"{GROUND_URL}/outbreaks")
            res.raise_for_status()
            outbreaks = res.json()
            logger.info(f"Found {len(outbreaks)} active outbreak clusters.")

            for ob in outbreaks:
                cluster_id = ob.get("cluster_id")
                centroid = ob.get("centroid")
                if not centroid or len(centroid) != 2:
                    logger.warning(f"Cluster {cluster_id} has no usable centroid; skipping.")
                    continue

                try:
                    ring = await _fetch_ring(client, centroid)
                except Exception as e:
                    logger.error(f"Ring lookup failed for cluster {cluster_id}: {e}")
                    continue

                phones = [p["farmer_phone"] for p in ring.get("plots", []) if p.get("farmer_phone")]
                if not phones:
                    logger.info(f"Cluster {cluster_id}: no reachable plots in the ring; nothing to send.")
                    continue

                districts = ring.get("districts") or []
                alert_payload = {
                    "cluster_id": cluster_id,
                    "disease": ob.get("disease", "Crop Disease"),
                    "district": ", ".join(districts) if districts else "your area",
                    "affected_plots_count": ob.get("distinct_plots", ob.get("report_count", 0)),
                    "alert_ring_km": ob.get("alert_ring_km", ALERT_RING_KM),
                    "farmer_phones": phones,
                }

                res_alert = await client.post(f"{CHANNEL_URL}/push-alert", json=alert_payload)
                res_alert.raise_for_status()
                dispatched += len(phones)
                logger.info(
                    f"Cluster {cluster_id}: dispatched ring alert to {len(phones)} plots "
                    f"across {districts or ['unknown']}."
                )

    except Exception as e:
        logger.error(f"Outbreak Radar worker exception: {e}", exc_info=True)
        return 0

    logger.info(f"Sweep complete — {dispatched} pre-emptive alerts dispatched.")
    return dispatched


def main(request=None):
    """Cloud Function entry point for Cloud Scheduler."""
    dispatched = asyncio.run(run_outbreak_radar())
    return f"OK — {dispatched} alerts dispatched", 200


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
