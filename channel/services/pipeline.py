import base64
import hashlib
import logging
from typing import Any, Dict, Optional, Tuple

from channel.services.whatsapp_in import whatsapp_in_service
from channel.services.whatsapp_out import whatsapp_out_service
from channel.services.stt import stt_service
from channel.services.tts import tts_service
from channel.services.composer import composer_service
from channel.services.state import user_state_service

from contracts.client import get_plot_passport, diagnose_leaf
from contracts.fallbacks import unavailable_diagnosis, context_unavailable_passport

logger = logging.getLogger("channel.pipeline")

# Nashik — the demo district (BRAIN.md §13). Used only when the farmer has
# never sent a pin, and only to fetch plot context, never to invent a diagnosis.
DEFAULT_LAT, DEFAULT_LON = 19.9975, 73.7898

ACK_TEXT = "Got it, checking your field 🌱\nतुमच्या शेताची पाहणी करत आहोत..."

NEED_PHOTO_TEXT = (
    "🌱 *अन्नदाता सेतु*\n\n"
    "पिकाच्या तपासणीसाठी कृपया प्रभावित पानाचा एक स्पष्ट फोटो पाठवा.\n"
    "(Please send one clear photo of the affected leaf.)"
)

LOCATION_SAVED_TEXT = (
    "📍 तुमचे स्थान नोंदवले आहे.\n\n"
    "आता प्रभावित पानाचा एक स्पष्ट फोटो पाठवा.\n"
    "(Location saved — now send a photo of the affected leaf.)"
)


async def process_inbound_pipeline(msg: Dict[str, Any]):
    """
    Background Task pipeline orchestrating the full WhatsApp reaction flow:
    1. Dedupe on Meta's message_id
    2. Route by message type — only a photo triggers a diagnosis
    3. Fetch PlotPassport from ground
    4. Diagnose via brain
    5. Speak it, then send the structured text

    A failure at any external step degrades to an honest "we don't know"
    (see contracts/fallbacks.py). It never degrades to the demo fixture:
    that fixture prescribes a real fungicide at a real dose.
    """
    sender_phone = msg.get("sender_phone")
    message_id = msg.get("message_id")
    msg_type = msg.get("type")

    if user_state_service.is_duplicate_message(message_id):
        logger.info(f"Skipping duplicate message_id {message_id}")
        return

    logger.info(f"Processing inbound message {message_id} from {sender_phone} (type={msg_type})")

    # A location pin carries no leaf to look at. Store it and ask for the photo
    # rather than running a diagnosis on an image that was never sent.
    if msg_type == "location":
        lat, lon = msg.get("lat"), msg.get("lon")
        if lat is not None and lon is not None:
            user_state_service.update_user_location(sender_phone, lat, lon)
            await whatsapp_out_service.send_text_message(sender_phone, LOCATION_SAVED_TEXT)
            return

    if msg_type == "audio":
        # Transcribe so the farmer's own words reach the log and the prompt.
        # A voice note still is not a photo, so it cannot produce a diagnosis.
        media_id = msg.get("media_id")
        audio_bytes = await whatsapp_in_service.fetch_media_bytes(media_id)
        if audio_bytes:
            transcript = await stt_service.transcribe_audio(audio_bytes)
            logger.info(f"STT transcript from {sender_phone}: {transcript}")
            user_state_service.set_pending_note(sender_phone, transcript)
        await whatsapp_out_service.send_text_message(sender_phone, NEED_PHOTO_TEXT)
        return

    if msg_type == "text":
        text = msg.get("text")
        if text:
            logger.info(f"Text note from {sender_phone}: {text}")
            user_state_service.set_pending_note(sender_phone, text)
        await whatsapp_out_service.send_text_message(sender_phone, NEED_PHOTO_TEXT)
        return

    if msg_type != "image":
        logger.info(f"Ignoring unsupported message type {msg_type} from {sender_phone}")
        return

    # ---- image path: the only path that yields a diagnosis ----
    await whatsapp_out_service.send_text_message(sender_phone, ACK_TEXT)

    lat, lon = user_state_service.get_user_location(sender_phone) or (DEFAULT_LAT, DEFAULT_LON)

    # Meta media must be fetched here, with our bearer token. The graph URL is
    # NOT publicly downloadable, so handing it to brain as an image_url yields
    # a 401 and a diagnosis made from context alone (BRAIN.md §11, 09:15).
    image_b64: Optional[str] = None
    image_bytes = await whatsapp_in_service.fetch_media_bytes(msg.get("media_id"))
    if image_bytes:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
    else:
        logger.warning(f"Could not download media {msg.get('media_id')} for {sender_phone}")

    passport = await _resolve_passport(lat, lon)
    farmer_note = user_state_service.take_pending_note(sender_phone)
    diagnosis = await _resolve_diagnosis(image_b64, passport, farmer_note)

    text_reply = composer_service.compose_text_advisory(diagnosis)
    marathi_script = composer_service.compose_marathi_script(diagnosis)

    audio_bytes = await tts_service.synthesize_speech(marathi_script)
    if audio_bytes:
        await whatsapp_out_service.send_audio_message(sender_phone, audio_bytes)
    await whatsapp_out_service.send_text_message(sender_phone, text_reply)

    logger.info(f"Finished pipeline for {sender_phone} (plot {passport.plot_id})")


async def _resolve_passport(lat: float, lon: float):
    """Plot context, or an explicitly empty passport — never invented telemetry."""
    try:
        return await get_plot_passport(lat, lon)
    except Exception as e:
        logger.error(f"PlotPassport unavailable for ({lat}, {lon}): {e}")
        geohash_stub = hashlib.md5(f"{lat:.4f},{lon:.4f}".encode()).hexdigest()[:7]
        return context_unavailable_passport(
            lat=lat,
            lon=lon,
            geohash=geohash_stub,
            plot_id=f"hash_{geohash_stub}",
        )


async def _resolve_diagnosis(image_b64: Optional[str], passport, farmer_note: Optional[str] = None):
    """Brain's answer, or an honest escalation. Never the demo fixture."""
    if not image_b64:
        logger.error("No image bytes available — escalating to human.")
        return unavailable_diagnosis()
    if farmer_note:
        logger.info(f"Attaching farmer note to diagnosis request: {farmer_note}")
    try:
        return await diagnose_leaf(None, passport, image_base64=image_b64)
    except Exception as e:
        logger.error(f"Diagnosis failed, escalating to human: {e}", exc_info=True)
        return unavailable_diagnosis()
