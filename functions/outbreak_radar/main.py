import os
import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger("functions.outbreak_radar")

CHANNEL_URL = os.getenv("CHANNEL_URL", "http://localhost:8001")
GROUND_URL = os.getenv("GROUND_URL", "http://localhost:8003")

async def run_outbreak_radar():
    """
    Cloud Function Gen2 scheduled worker (cron: */30 * * * *):
    1. Query active outbreaks from ground service.
    2. For each hotspot cluster, push pre-emptive 15km ring warnings to channel service.
    """
    logger.info("Executing scheduled Outbreak Radar sweep...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: Get active outbreaks
            res = await client.get(f"{GROUND_URL}/outbreaks")
            if res.status_code != 200:
                logger.error(f"Failed to fetch outbreaks: {res.status_code}")
                return

            outbreaks = res.json()
            logger.info(f"Found {len(outbreaks)} active outbreak clusters.")

            for ob in outbreaks:
                cluster_id = ob.get("cluster_id")
                disease = ob.get("disease", "Crop Disease")
                report_count = ob.get("report_count", 5)

                # Step 2: Push ring alert
                alert_payload = {
                    "cluster_id": cluster_id,
                    "disease": disease,
                    "district": "Nashik",
                    "affected_plots_count": report_count,
                    "alert_ring_km": 15.0,
                    "farmer_phones": [
                        "919876543210",
                        "919876543211",
                        "919876543212"
                    ]
                }
                res_alert = await client.post(f"{CHANNEL_URL}/push-alert", json=alert_payload)
                logger.info(f"Pushed ring alert for cluster {cluster_id}: Status {res_alert.status_code}")

    except Exception as e:
        logger.error(f"Outbreak Radar worker exception: {e}")

def main(request=None):
    """Cloud Function entry point for Cloud Scheduler."""
    import asyncio
    asyncio.run(run_outbreak_radar())
    return "OK", 200

if __name__ == "__main__":
    main()
