import logging
from typing import List, Dict
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from collections import defaultdict

from channel.services.whatsapp_out import whatsapp_out_service
from channel.services.tts import tts_service
from channel.services.state import user_state_service
from channel.services.phrasebook import phrases
from contracts.languages import DEFAULT_LANGUAGE, get

logger = logging.getLogger("channel.router.alerts")

router = APIRouter(prefix="", tags=["Outbreak Ring Alerts"])

class AlertRingRequest(BaseModel):
    cluster_id: str
    disease: str
    district: str
    affected_plots_count: int
    alert_ring_km: float = 15.0
    farmer_phones: List[str]

def _language_of(phone: str) -> str:
    """The alert language for one farmer in the ring.

    A ring alert arrives unprompted, so there is no inbound message to read a
    language from — only what this farmer has already told us. Someone who has
    never messaged us gets the default; the region layer is unavailable here
    because the radar sends phone numbers, not plots.
    """
    return (
        user_state_service.get_user_language(phone)
        or user_state_service.get_detected_language(phone)
        or DEFAULT_LANGUAGE
    )


async def send_ring_alerts_task(req: AlertRingRequest):
    """Background task fanning out pre-emptive WhatsApp ring alerts to farmers in 15km zone.

    Grouped by language, not sent one at a time: the audio for a ring alert is
    identical for every farmer who shares a language, so this is one TTS call
    per language present in the ring rather than one per farmer. A 42-farmer
    ring speaking two languages costs two syntheses, as it did when everyone
    was assumed to speak Marathi.
    """
    by_language = defaultdict(list)
    for phone in req.farmer_phones:
        by_language[_language_of(phone)].append(phone)

    logger.info(
        f"Ring alert for cluster {req.cluster_id} spans {len(by_language)} language(s): "
        + ", ".join(f"{code}={len(nums)}" for code, nums in by_language.items())
    )

    delivered, failed = 0, 0
    for code, phones in by_language.items():
        lang = get(code)
        alert = phrases(lang.code)["alert"]
        fields = {
            "district": req.district,
            "disease": req.disease,
            "count": req.affected_plots_count,
        }
        alert_text = alert["text"].format(**fields)

        # Synthesised once per language and reused across its farmers.
        audio_bytes = await tts_service.synthesize_speech(
            alert["voice"].format(**fields), lang.bcp47
        )

        for phone in phones:
            try:
                if audio_bytes:
                    await whatsapp_out_service.send_audio_message(phone, audio_bytes)
                # send_text_message reports delivery via its return value; it does
                # not raise. Logging success unconditionally reported a full fan-out
                # while every message was in fact bouncing on a 401.
                if await whatsapp_out_service.send_text_message(phone, alert_text):
                    delivered += 1
                    logger.info(f"Pushed pre-emptive ring alert to farmer {phone} ({lang.code})")
                else:
                    failed += 1
                    logger.error(f"Ring alert to {phone} was not delivered.")
            except Exception as e:
                failed += 1
                logger.error(f"Failed to push ring alert to {phone}: {e}")

    logger.info(
        f"Ring alert fan-out for cluster {req.cluster_id}: "
        f"{delivered} delivered, {failed} failed, {len(req.farmer_phones)} targeted."
    )

@router.post("/push-alert")
async def push_ring_alert(req: AlertRingRequest, background_tasks: BackgroundTasks):
    """POST /push-alert — Called by outbreak_radar Cloud Function to push 15km ring alerts."""
    background_tasks.add_task(send_ring_alerts_task, req)
    return {"status": "alert_dispatched", "target_farmers": len(req.farmer_phones)}
