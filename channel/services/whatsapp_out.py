import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger("channel.whatsapp_out")

MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "mock_token")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "mock_phone_id")

class WhatsAppOutboundService:
    async def send_text_message(self, recipient_phone: str, text: str) -> bool:
        """Send a WhatsApp text message to farmer."""
        if MOCK:
            logger.info(f"[MOCK OUTBOUND TEXT] To {recipient_phone}:\n{text}")
            return True

        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": text}
        }

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                logger.info(f"Sent text message to {recipient_phone}")
                return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp text to {recipient_phone}: {e}")
            return False

    async def send_audio_message(self, recipient_phone: str, audio_bytes: bytes) -> bool:
        """
        Two-step WhatsApp Audio Upload & Send:
        1. Upload .ogg/opus binary file to Meta /media endpoint.
        2. Send audio message referencing uploaded media_id.
        """
        if MOCK:
            logger.info(f"[MOCK OUTBOUND AUDIO] Sent {len(audio_bytes)} bytes audio note to {recipient_phone}")
            return True

        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Upload media to Meta
                upload_url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/media"
                files = {
                    "file": ("voice_note.ogg", audio_bytes, "audio/ogg; codecs=opus"),
                    "type": (None, "audio/ogg"),
                    "messaging_product": (None, "whatsapp")
                }
                res1 = await client.post(upload_url, headers=headers, files=files)
                res1.raise_for_status()
                media_id = res1.json().get("id")

                # Step 2: Send audio payload
                msg_url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
                json_payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient_phone,
                    "type": "audio",
                    "audio": {"id": media_id}
                }
                res2 = await client.post(msg_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}, json=json_payload)
                res2.raise_for_status()
                logger.info(f"Sent voice note to {recipient_phone} (media_id: {media_id})")
                return True
        except Exception as e:
            logger.error(f"Failed to send voice note to {recipient_phone}: {e}")
            return False

whatsapp_out_service = WhatsAppOutboundService()
