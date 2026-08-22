import logging
from typing import List, Dict
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from channel.services.whatsapp_out import whatsapp_out_service
from channel.services.tts import tts_service

logger = logging.getLogger("channel.router.alerts")

router = APIRouter(prefix="", tags=["Outbreak Ring Alerts"])

class AlertRingRequest(BaseModel):
    cluster_id: str
    disease: str
    district: str
    affected_plots_count: int
    alert_ring_km: float = 15.0
    farmer_phones: List[str]

async def send_ring_alerts_task(req: AlertRingRequest):
    """Background task fanning out pre-emptive WhatsApp ring alerts to farmers in 15km zone."""
    alert_text = (
        f"🚨 *सावधान! पूर्वसूचना (Outbreak Alert)* 🚨\n\n"
        f"तुमच्या परिसरामध्ये ({req.district}) *{req.disease}* रोगाचा प्रादुर्भाव आढळून आला आहे. "
        f"एकूण {req.affected_plots_count} शेतांमध्ये हा रोग पसरला आहे.\n\n"
        f"🛡️ *संरक्षक उपाय:* आपल्या पिकाची पाहणी करा. रोग तुमच्या शेतात येण्यापूर्वी "
        f"खबरदारीची फवारणी करा किंवा पानाचा फोटो काढून येथे पाठवा."
    )

    marathi_script = (
        f"सावधान! तुमच्या {req.district} परिसरामध्ये {req.disease} रोगाचा प्रादुर्भाव सुरू झाला आहे. "
        f"{req.affected_plots_count} शेतांमध्ये हा रोग दिसून आला आहे. "
        f"रोग तुमच्या पिकावर येण्यापूर्वी खबरदारी घ्या किंवा तुमच्या शेताचा फोटो आम्हाला पाठवा."
    )

    audio_bytes = await tts_service.synthesize_speech(marathi_script)

    for phone in req.farmer_phones:
        try:
            if audio_bytes:
                await whatsapp_out_service.send_audio_message(phone, audio_bytes)
            await whatsapp_out_service.send_text_message(phone, alert_text)
            logger.info(f"Pushed pre-emptive ring alert to farmer {phone}")
        except Exception as e:
            logger.error(f"Failed to push ring alert to {phone}: {e}")

@router.post("/push-alert")
async def push_ring_alert(req: AlertRingRequest, background_tasks: BackgroundTasks):
    """POST /push-alert — Called by outbreak_radar Cloud Function to push 15km ring alerts."""
    background_tasks.add_task(send_ring_alerts_task, req)
    return {"status": "alert_dispatched", "target_farmers": len(req.farmer_phones)}
