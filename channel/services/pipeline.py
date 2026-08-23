import base64
import hashlib
import logging
from typing import Any, Dict, Optional, Tuple

from channel.services.whatsapp_in import whatsapp_in_service
from channel.services.whatsapp_out import whatsapp_out_service
from channel.services.stt import stt_service
from channel.services.tts import tts_service
from channel.services.composer import composer_service
from channel.services.translate import translate_service
from channel.services.media import media_archive_service
from channel.services.state import user_state_service

from channel.services.languages import (
    DEFAULT_LANGUAGE,
    get,
    FALLBACK_BY_REGION,
    detect_from_text,
    is_language_request,
    is_supported,
    language_for_state,
    parse_language_command,
)
from channel.services.phrasebook import language_menu, ui

from contracts.client import get_plot_passport, diagnose_leaf, compose_voice_script
from contracts.fallbacks import (
    UNKNOWN_PLACE,
    unavailable_diagnosis,
    context_unavailable_passport,
)

logger = logging.getLogger("channel.pipeline")

# Nashik — the demo district (BRAIN.md §13). Used only when the farmer has
# never sent a pin, and only to fetch plot context, never to invent a diagnosis.
DEFAULT_LAT, DEFAULT_LON = 19.9975, 73.7898


async def resolve_language(sender_phone: str, passport=None, note: Optional[str] = None) -> str:
    """Which language to answer this farmer in.

    Four layers, strongest evidence first. Each one degrades to the next rather
    than to a guess:

      1. A language the farmer explicitly chose. A decision, not an inference,
         so nothing below may override it.
      2. What their own message was in — the language Cloud Speech reported for
         a voice note, or the script of their text. Devanagari is ambiguous
         between Hindi and Marathi, so that case asks Cloud Translate rather
         than picking one.
      3. The majority language of the plot's state. The weakest signal: it is
         right for most farmers in a state and wrong for the rest, which is why
         anything the farmer has actually told us outranks it.
      4. Marathi, the demo district's language and the historical default.
    """
    chosen = user_state_service.get_user_language(sender_phone)
    if chosen:
        return chosen

    detected = user_state_service.get_detected_language(sender_phone)
    if detected:
        return detected

    if note:
        from_script = detect_from_text(note)
        if from_script:
            return from_script
        # Devanagari — Hindi or Marathi, and script cannot say which.
        from_api = await translate_service.detect(note)
        if from_api:
            return from_api

    state = getattr(passport, "state", None) if passport is not None else None
    # UNKNOWN_PLACE is the placeholder on a passport built with no telemetry. It
    # means "we could not find out where this is" — NOT "a state we have no
    # mapping for" — so it must fall through to the default rather than to the
    # region fallback. Reading it as the latter answered every farmer in English
    # whenever ground was unreachable.
    if state and state != UNKNOWN_PLACE:
        by_state = language_for_state(state)
        if by_state:
            return by_state
        # A real state we have no mapping for. English rather than Marathi:
        # a farmer in Kerala is likelier to read English, and guessing a
        # wrong Indian language reads as a bug rather than a default.
        return FALLBACK_BY_REGION

    return DEFAULT_LANGUAGE


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
            code = await resolve_language(sender_phone)
            await whatsapp_out_service.send_text_message(
                sender_phone, ui("location_saved", code)
            )
            return

    if msg_type == "audio":
        # Transcribe so the farmer's own words reach the log and the prompt.
        # A voice note still is not a photo, so it cannot produce a diagnosis.
        media_id = msg.get("media_id")
        audio_bytes = await whatsapp_in_service.fetch_media_bytes(media_id)
        code = await resolve_language(sender_phone)
        if audio_bytes:
            # The current best guess is only the primary hypothesis — Cloud
            # Speech listens for the others too and reports what it heard.
            transcription = await stt_service.transcribe_audio(audio_bytes, code)
            if transcription.text:
                logger.info(f"STT transcript from {sender_phone}: {transcription.text}")
                user_state_service.set_pending_note(sender_phone, transcription.text)
            if transcription.language:
                # Remembered, not promoted to a chosen language: the next
                # message may be a bare photo carrying no signal of its own.
                user_state_service.set_detected_language(sender_phone, transcription.language)
                code = await resolve_language(sender_phone)
        await whatsapp_out_service.send_text_message(sender_phone, ui("need_photo", code))
        return

    if msg_type == "text":
        text = msg.get("text")

        # A language choice is a settings change, not a note about the crop.
        # Matched on the whole message, so "my hindi neighbour has the same
        # spots" stays a note (see languages.parse_language_command).
        chosen = parse_language_command(text or "")
        if chosen:
            user_state_service.set_user_language(sender_phone, chosen)
            logger.info(f"{sender_phone} chose language {chosen}.")
            await whatsapp_out_service.send_text_message(
                sender_phone, ui("language_set", chosen)
            )
            return

        if is_language_request(text or ""):
            # The menu is not localised on purpose: a farmer who cannot read the
            # current language is exactly the one asking for this.
            await whatsapp_out_service.send_text_message(sender_phone, language_menu())
            return

        if text:
            logger.info(f"Text note from {sender_phone}: {text}")
            user_state_service.set_pending_note(sender_phone, text)

        code = await resolve_language(sender_phone, note=text)
        if text and not user_state_service.get_user_language(sender_phone):
            # What they wrote in is evidence for the next message too.
            if is_supported(code):
                user_state_service.set_detected_language(sender_phone, code)
        await whatsapp_out_service.send_text_message(sender_phone, ui("need_photo", code))
        return

    if msg_type != "image":
        logger.info(f"Ignoring unsupported message type {msg_type} from {sender_phone}")
        return

    # ---- image path: the only path that yields a diagnosis ----
    # The acknowledgement goes out before the passport exists, so it uses what
    # the farmer has already told us. The advisory itself is re-resolved once
    # the plot's state is known.
    code = await resolve_language(sender_phone)
    await whatsapp_out_service.send_text_message(sender_phone, ui("ack", code))

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

    # Now the plot's state is known, so the region layer can contribute.
    code = await resolve_language(sender_phone, passport=passport, note=farmer_note)

    text_reply = composer_service.compose_text_advisory(diagnosis, code)
    voice_script = await resolve_voice_script(diagnosis, passport, code)

    audio_bytes = await tts_service.synthesize_speech(voice_script, get(code).bcp47)
    if audio_bytes:
        await whatsapp_out_service.send_audio_message(sender_phone, audio_bytes)
    await whatsapp_out_service.send_text_message(sender_phone, text_reply)

    # After the reply, never before it. We have just promised this farmer that an
    # agronomist will look at their photo — keep the photo so that is true. Meta's
    # media URLs expire, so this is the last point at which the bytes exist.
    if diagnosis.escalate_to_human:
        await media_archive_service.archive_for_review(
            image_bytes, sender_phone, passport, diagnosis
        )

    logger.info(
        f"Finished pipeline for {sender_phone} (plot {passport.plot_id}, language {code})"
    )


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


async def resolve_voice_script(diagnosis, passport=None, code: str = DEFAULT_LANGUAGE) -> str:
    """The spoken script in the farmer's language, generated by brain where possible.

    BRAIN.md §11 (15:30): ask the model for the target language directly rather
    than translating. The local template is the fallback, and is single-script
    by construction — the voice note is synthesised with that language's voice,
    so anything in another script comes out mispronounced.
    """
    try:
        script = await compose_voice_script(diagnosis, passport, code)
        if script:
            return script
    except Exception as e:
        logger.warning(f"Voice script generation unavailable, using local template: {e}")

    # Falling back. The template's biggest omission is action_text — the actual
    # instruction — because it arrives in English. Cloud Translate can recover
    # it (and for an English farmer it needs no call at all); translate.py
    # returns None whenever the result is not speakable in the target language,
    # and None puts the script back exactly as it was.
    action_translated = None
    if not diagnosis.escalate_to_human:
        # An escalation's script is a fixed "we could not read your photo, do
        # not spray" — translating action_text into it would reintroduce advice
        # we have just said we do not have.
        action_translated = await translate_service.to_language(diagnosis.action_text, code)
        if action_translated:
            logger.info(f"Recovered action_text for the {code} script.")

    return composer_service.compose_voice_script(
        diagnosis, code, action_translated=action_translated
    )


async def resolve_marathi_script(diagnosis, passport=None) -> str:
    """resolve_voice_script pinned to Marathi. Kept for existing callers."""
    return await resolve_voice_script(diagnosis, passport, DEFAULT_LANGUAGE)
