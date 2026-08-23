"""Cloud Storage archive for photos awaiting human review.

`google-cloud-storage` has been in channel/requirements.txt since the start
without a single import. This is what it was for.

When a diagnosis escalates, both the text reply and the voice note tell the
farmer that "आमचे कृषी तज्ज्ञ तुमचा फोटो तपासून लवकरच सल्ला देतील" — an
agronomist will look at your photo. Nothing kept the photo. The bytes were
fetched from Meta, base64'd to brain, and dropped when the request ended; Meta's
media URLs expire, so by the time anyone went looking there was nothing to look
at. The promise could not be kept.

Archiving is best-effort and runs after the farmer already has their reply, so a
storage outage costs the review queue, never the advisory.

ON THE PHONE NUMBER
The object path uses a salted hash of the sender, not the number. A reviewer
needs to know that two photos came from the same farmer; they do not need the
number to do the review, and object paths turn up in logs, bucket listings and
access records. Set MEDIA_HASH_SALT to keep those hashes from being reversible
by enumerating India's mobile range — an unsalted hash of a 10-digit number is
not an anonymisation of anything.
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("channel.media")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
BUCKET = os.getenv("MEDIA_ARCHIVE_BUCKET")
HASH_SALT = os.getenv("MEDIA_HASH_SALT", "")
TIMEOUT_S = 10.0
PREFIX = "review-queue"


def _sender_ref(sender_phone: str) -> str:
    """Stable, non-reversible reference for a sender."""
    digest = hashlib.sha256(f"{HASH_SALT}{sender_phone}".encode()).hexdigest()
    return digest[:16]


class MediaArchiveService:
    def __init__(self):
        self.bucket = None
        self._init_client()

    def _init_client(self):
        if MOCK or not BUCKET:
            logger.info(
                "MediaArchiveService off (MOCK_MODE or MEDIA_ARCHIVE_BUCKET unset) — "
                "escalated photos will not be retained for review."
            )
            return

        try:
            from google.cloud import storage

            # Bucket handle only — no existence check here. get_bucket() would
            # add a network round trip to import time and take the whole service
            # down with it if storage were briefly unreachable at boot.
            self.bucket = storage.Client().bucket(BUCKET)
            logger.info(f"Media archive ready: gs://{BUCKET}/{PREFIX}/")
        except Exception as e:
            logger.warning(f"Failed to initialize Cloud Storage client: {e}. Archive off.")

    @property
    def is_available(self) -> bool:
        return self.bucket is not None

    def _upload_blocking(self, path: str, image_bytes: bytes, metadata: Dict[str, str]) -> str:
        blob = self.bucket.blob(path)
        # Metadata rather than a sidecar file: it survives with the object and a
        # reviewer listing the bucket can see the context without a second read.
        blob.metadata = metadata
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        return f"gs://{BUCKET}/{path}"

    async def archive_for_review(
        self,
        image_bytes: Optional[bytes],
        sender_phone: str,
        passport,
        diagnosis,
    ) -> Optional[str]:
        """Store one photo for the review queue. Returns its URI, or None."""
        if not image_bytes or not self.bucket:
            return None

        now = datetime.now(timezone.utc)
        ref = _sender_ref(sender_phone)
        # Date-partitioned so a reviewer can work a day at a time and a lifecycle
        # rule can expire old entries without parsing object names.
        path = (
            f"{PREFIX}/{now:%Y/%m/%d}/{ref}/"
            f"{now:%H%M%S}-{passport.plot_id}.jpg"
        )
        metadata = {
            "plot_id": passport.plot_id,
            "geohash": passport.geohash,
            "district": passport.district,
            "crop": passport.inferred_crop,
            "confidence": str(diagnosis.confidence),
            "reason": "escalate_to_human",
            "captured_at": now.isoformat(),
        }

        try:
            uri = await asyncio.wait_for(
                asyncio.to_thread(self._upload_blocking, path, image_bytes, metadata),
                timeout=TIMEOUT_S,
            )
            logger.info(f"Archived escalated photo for review: {uri}")
            return uri
        except asyncio.TimeoutError:
            logger.warning(f"Media archive upload timed out after {TIMEOUT_S}s.")
            return None
        except Exception as e:
            logger.warning(f"Media archive upload failed: {e}")
            return None

    def status(self) -> Dict[str, Any]:
        return {
            "available": self.is_available,
            "bucket": BUCKET,
            "salted": bool(HASH_SALT),
        }


media_archive_service = MediaArchiveService()
