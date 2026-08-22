import os
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("channel.whatsapp_in")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "mock_token")

class WhatsAppInboundService:
    def extract_message(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse raw Meta WhatsApp webhook payload into standardized message format."""
        try:
            entry = payload.get("entry", [])[0]
            changes = entry.get("changes", [])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                # Might be a status update (sent/delivered/read) — ignore
                return None

            msg = messages[0]
            sender_phone = msg.get("from")
            message_id = msg.get("id")
            timestamp = msg.get("timestamp")
            msg_type = msg.get("type")

            result = {
                "sender_phone": sender_phone,
                "message_id": message_id,
                "timestamp": timestamp,
                "type": msg_type,
                "text": None,
                "media_id": None,
                "lat": None,
                "lon": None
            }

            if msg_type == "text":
                result["text"] = msg.get("text", {}).get("body")
            elif msg_type == "image":
                result["media_id"] = msg.get("image", {}).get("id")
                result["caption"] = msg.get("image", {}).get("caption")
            elif msg_type == "audio":
                result["media_id"] = msg.get("audio", {}).get("id")
            elif msg_type == "location":
                loc = msg.get("location", {})
                result["lat"] = loc.get("latitude")
                result["lon"] = loc.get("longitude")

            return result
        except Exception as e:
            logger.error(f"Error extracting Meta message payload: {e}")
            return None

    async def fetch_media_bytes(self, media_id: str) -> Optional[bytes]:
        """
        Two-step Meta media download:
        1. Fetch media URL using media_id with Bearer token.
        2. Download binary bytes from media URL.
        """
        if MOCK or not media_id:
            logger.info(f"Mock fetching media bytes for ID {media_id}")
            return b"mock_binary_image_data"

        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Get media URL
                meta_url = f"https://graph.facebook.com/v19.0/{media_id}"
                res1 = await client.get(meta_url, headers=headers)
                res1.raise_for_status()
                download_url = res1.json().get("url")

                # Step 2: Download media file
                res2 = await client.get(download_url, headers=headers)
                res2.raise_for_status()
                return res2.content
        except Exception as e:
            logger.error(f"Failed to fetch WhatsApp media for ID {media_id}: {e}")
            return None

whatsapp_in_service = WhatsAppInboundService()
