import logging
from typing import Dict, Any

from channel.services.whatsapp_in import whatsapp_in_service
from channel.services.whatsapp_out import whatsapp_out_service
from channel.services.stt import stt_service
from channel.services.tts import tts_service
from channel.services.composer import composer_service
from channel.services.state import user_state_service

from contracts.client import get_plot_passport, diagnose_leaf

logger = logging.getLogger("channel.pipeline")

async def process_inbound_pipeline(msg: Dict[str, Any]):
    """
    Background Task pipeline orchestrates the full WhatsApp reaction flow:
    1. Dedupe message_id
    2. Send instant acknowledgement
    3. Parse text / STT audio / image / location
    4. Fetch PlotPassport from Ground service
    5. Call Gemini Brain for Diagnosis
    6. Synthesize TTS Marathi voice note
    7. Send voice note & text reply to farmer
    """
    sender_phone = msg.get("sender_phone")
    message_id = msg.get("message_id")
    msg_type = msg.get("type")

    if user_state_service.is_duplicate_message(message_id):
        logger.info(f"Skipping duplicate message_id {message_id}")
        return

    logger.info(f"Processing inbound message {message_id} from {sender_phone} (Type: {msg_type})")

    # 1. Send instant ack
    await whatsapp_out_service.send_text_message(
        sender_phone,
        "Got it, checking your field 🌱\nतुमच्या शेताची पाहणी करत आहोत..."
    )

    # Default coordinates (Nashik) if location missing
    lat, lon = 19.9975, 73.7898

    # 2. Extract input components
    image_url = None
    if msg_type == "location":
        lat, lon = msg.get("lat"), msg.get("lon")
        user_state_service.update_user_location(sender_phone, lat, lon)
    elif msg_type == "audio":
        media_id = msg.get("media_id")
        audio_bytes = await whatsapp_in_service.fetch_media_bytes(media_id)
        if audio_bytes:
            transcript = await stt_service.transcribe_audio(audio_bytes)
            logger.info(f"STT Transcript: {transcript}")
    elif msg_type == "image":
        media_id = msg.get("media_id")
        # Reuse user's cached location if available
        user_loc = user_state_service.get_user_location(sender_phone)
        if user_loc:
            lat, lon = user_loc
        image_url = f"https://graph.facebook.com/v19.0/{media_id}"

    # 3. Retrieve PlotPassport from Ground service
    try:
        passport = await get_plot_passport(lat, lon)
    except Exception as e:
        logger.error(f"Failed to retrieve PlotPassport: {e}")
        from contracts.mock_data import PASSPORT as passport

    # 4. Diagnose leaf via Brain service
    try:
        diagnosis = await diagnose_leaf(image_url or "http://mock.url/leaf.jpg", passport)
    except Exception as e:
        logger.error(f"Failed to diagnose leaf: {e}")
        from contracts.mock_data import DIAGNOSIS as diagnosis

    # 5. Compose formatted text and Marathi voice script
    text_reply = composer_service.compose_text_advisory(diagnosis)
    marathi_script = composer_service.compose_marathi_script(diagnosis)

    # 6. Synthesize TTS Marathi audio file
    audio_bytes = await tts_service.synthesize_speech(marathi_script)

    # 7. Send voice note first, then structured text
    if audio_bytes:
        await whatsapp_out_service.send_audio_message(sender_phone, audio_bytes)
    await whatsapp_out_service.send_text_message(sender_phone, text_reply)

    logger.info(f"Successfully finished processing pipeline for {sender_phone}")
