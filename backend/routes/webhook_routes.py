"""
routes/webhook_routes.py
------------------------
Vapi webhook endpoint — called by Vapi (not the React frontend).

Vapi uses a SINGLE webhook URL and sends multiple event types,
distinguished by `message.type`:

    - "status-update"        : call lifecycle (queued/ringing/in-progress/ended)
    - "transcript"           : real-time transcript chunks
    - "end-of-call-report"   : final transcript + analysis (summary, etc.)

We persist:
    - Call.status / Call.ended_at  from status-update
    - Message rows                 from transcript + end-of-call-report
    - Call.summary                 from end-of-call-report
    - Client.extracted_information from end-of-call-report (via Groq)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import Config
from database import get_db
from models import Call, Message
from services import ai_service, extraction_service, memory_service
from utils.logger import get_logger


logger = get_logger("webhook_routes")

router = APIRouter()


# ---------------------------------------------------------------------
# Status mapping: Vapi statuses -> our internal statuses
# ---------------------------------------------------------------------

# Vapi call.status values: "queued" | "ringing" | "in-progress" | "forwarding" | "ended"
_VAPI_STATUS_MAP = {
    "queued": "initiated",
    "ringing": "initiated",
    "in-progress": "answered",
    "forwarding": "in-progress",
    "ended": "completed",
}

# Vapi endedReason values that mean the call did NOT succeed.
_FAILED_END_REASONS = {
    "customer-did-not-answer",
    "customer-busy",
    "customer-did-not-give-microphone-permission",
    "voicemail",
    "phone-call-provider-closed-websocket",
    "twilio-failed-to-connect-call",
}


# ---------------------------------------------------------------------
# Single webhook entry point
# ---------------------------------------------------------------------

@router.post("/vapi-webhook")
def vapi_webhook(
    request: Request,
    body: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    """Receive every event Vapi sends about a call."""

    # --- Optional webhook secret check ---
    if Config.VAPI_WEBHOOK_SECRET:
        incoming = request.headers.get("X-Vapi-Secret", "")
        if incoming != Config.VAPI_WEBHOOK_SECRET:
            logger.warning("Rejected webhook with bad/missing secret.")
            return JSONResponse(status_code=401, content={"error": "unauthorized"})

    message = body.get("message") or {}
    msg_type = message.get("type")

    if not msg_type:
        return {"ok": True}

    # Vapi nests the call object under message.call
    vapi_call = message.get("call") or {}
    vapi_call_id = vapi_call.get("id")

    # 1) Try to match by Vapi's call id (which we save as Call.call_sid).
    call = (
        db.query(Call).filter_by(call_sid=vapi_call_id).first()
        if vapi_call_id
        else None
    )

    # 2) Fallback: match by metadata.local_call_id (we embed this on every
    #    call we create — both phone and web).
    if not call:
        metadata = _extract_metadata(vapi_call)
        local_id = metadata.get("local_call_id") if metadata else None
        if local_id:
            try:
                call = db.get(Call, int(local_id))
            except (TypeError, ValueError):
                call = None
            if call and vapi_call_id and not call.call_sid:
                call.call_sid = vapi_call_id
                db.commit()

    logger.info(
        "Vapi webhook: type=%s vapi_call_id=%s local_call_id=%s matched=%s",
        msg_type, vapi_call_id, call.id if call else None, bool(call),
    )

    try:
        if msg_type == "status-update":
            _handle_status_update(db, call, message)
        elif msg_type == "transcript":
            _handle_transcript_chunk(db, call, message)
        elif msg_type == "end-of-call-report":
            _handle_end_of_call(db, call, message)
        else:
            logger.info("Ignoring Vapi event type: %s", msg_type)
    except Exception as exc:
        # Never 500 to Vapi — it will retry storms.
        logger.exception("Webhook handler error (%s): %s", msg_type, exc)

    return {"ok": True}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _extract_metadata(vapi_call: Dict) -> Dict:
    """
    Pull our `metadata` dict out of Vapi's call payload.

    Vapi has nested metadata in several places over different API versions:
        call.metadata
        call.assistantOverrides.metadata
        call.assistant.metadata
    Check all of them.
    """
    candidates = (
        vapi_call.get("metadata"),
        (vapi_call.get("assistantOverrides") or {}).get("metadata"),
        (vapi_call.get("assistant") or {}).get("metadata"),
    )
    for meta in candidates:
        if isinstance(meta, dict) and meta:
            return meta
    return {}


# ---------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------

def _handle_status_update(
    db: Session,
    call: Optional[Call],
    message: Dict,
) -> None:
    """Update Call.status / Call.ended_at when Vapi reports a lifecycle change."""
    if not call:
        return

    vapi_status = (message.get("status") or "").lower()
    new_status = _VAPI_STATUS_MAP.get(vapi_status, call.status)

    ended_reason = (message.get("endedReason") or "").lower()
    if vapi_status == "ended":
        if ended_reason in _FAILED_END_REASONS:
            new_status = "failed" if "answer" not in ended_reason else "no_answer"
        if not call.ended_at:
            call.ended_at = datetime.utcnow()

    call.status = new_status
    db.commit()


def _handle_transcript_chunk(
    db: Session,
    call: Optional[Call],
    message: Dict,
) -> None:
    """
    Save real-time transcript fragments so the dashboard can stream them.

    Vapi sends transcripts in chunks; we only persist FINAL chunks
    (transcriptType == "final") to avoid duplicate partial text.
    """
    if not call:
        return

    transcript_type = message.get("transcriptType")
    if transcript_type and transcript_type != "final":
        return

    role = (message.get("role") or "").lower()  # "user" or "assistant"
    text = (message.get("transcript") or "").strip()

    if not text or role not in {"user", "assistant"}:
        return

    # Skip if we've already saved the exact same final line for this call.
    duplicate = (
        db.query(Message)
        .filter_by(call_id=call.id, speaker=role, content=text)
        .first()
    )
    if duplicate:
        return

    memory_service.add_message(db, call.id, role, text)


def _handle_end_of_call(
    db: Session,
    call: Optional[Call],
    message: Dict,
) -> None:
    """
    Persist the full transcript, mark the call completed, save the summary,
    and run client-info extraction.
    """
    if not call:
        logger.warning("end-of-call-report for unknown call (no matching Call row).")
        return

    # 1) Backfill the full transcript from the report (in case we missed
    #    any live transcript events).
    artifact = message.get("artifact") or {}
    transcript_messages: List[Dict] = (
        artifact.get("messages")
        or message.get("messages")
        or []
    )
    for m in transcript_messages:
        role = (m.get("role") or "").lower()
        # Vapi uses "bot" in some payloads, "assistant" in others.
        if role == "bot":
            role = "assistant"
        if role not in {"user", "assistant"}:
            continue

        content = (m.get("message") or m.get("content") or "").strip()
        if not content:
            continue

        already = (
            db.query(Message)
            .filter_by(call_id=call.id, speaker=role, content=content)
            .first()
        )
        if already:
            continue

        msg = Message(call_id=call.id, speaker=role, content=content)
        db.add(msg)

    # 2) Mark the call completed (or failed) + record end time.
    ended_reason = (message.get("endedReason") or "").lower()
    if ended_reason in _FAILED_END_REASONS:
        call.status = "failed" if "answer" not in ended_reason else "no_answer"
    else:
        call.status = "completed"
    if not call.ended_at:
        call.ended_at = datetime.utcnow()

    # 3) Save Vapi's auto-generated summary if present, otherwise generate one.
    analysis = message.get("analysis") or {}
    vapi_summary = (analysis.get("summary") or "").strip()
    if vapi_summary:
        call.summary = vapi_summary

    db.commit()

    # If Vapi didn't provide a summary, ask Groq directly.
    if not call.summary:
        try:
            history = memory_service.get_recent_history(db, call.id, limit=500)
            transcript_lines = [f"{m['role']}: {m['content']}" for m in history]
            generated = ai_service.generate_call_summary(transcript_lines)
            if generated:
                call.summary = generated
                db.commit()
        except Exception as exc:
            logger.warning("Summary generation failed: %s", exc)

    # 4) Run structured info extraction on the full conversation.
    if call.client:
        try:
            history = memory_service.get_recent_history(db, call.id, limit=500)
            extraction_service.update_client_information(db, call.client, history)
        except Exception as exc:
            logger.warning("End-of-call extraction failed: %s", exc)
