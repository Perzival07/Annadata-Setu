import os
import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException, Query, BackgroundTasks

from channel.services.whatsapp_in import whatsapp_in_service
from channel.services.pipeline import process_inbound_pipeline

logger = logging.getLogger("channel.router.webhook")

router = APIRouter(prefix="", tags=["Meta WhatsApp Webhook"])

VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "annadata_setu_verify_token")

@router.get("/webhook")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """Meta WhatsApp Webhook Verification Endpoint."""
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Meta Webhook verified successfully!")
            return Response(content=challenge, media_type="text/plain")
        else:
            logger.warning("Meta Webhook verification token mismatch.")
            raise HTTPException(status_code=403, detail="Verification token mismatch")
    raise HTTPException(status_code=400, detail="Missing verification parameters")

@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Inbound Meta WhatsApp Event Handler.
    MUST return HTTP 200 within 3 seconds to avoid duplicate retries from Meta.
    Heavy processing is offloaded to FastAPI BackgroundTasks.
    """
    try:
        payload = await request.json()
        msg = whatsapp_in_service.extract_message(payload)

        if msg:
            logger.info(f"Enqueuing message_id {msg.get('message_id')} for background execution.")
            background_tasks.add_task(process_inbound_pipeline, msg)

        # Always return HTTP 200 OK immediately
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}")
        return {"status": "error", "detail": str(e)}
