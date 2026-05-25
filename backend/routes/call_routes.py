"""
routes/call_routes.py
---------------------
Endpoints that *initiate* outbound calls via Vapi.

These are admin actions called from the React dashboard:
- POST /start-calls           -> call every client without a successful call yet
- POST /call/<client_id>      -> call one specific client
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import Config
from database import get_db
from models import Call, Client
from services.vapi_service import build_web_call_payload, start_outbound_call
from utils.logger import get_logger


logger = get_logger("call_routes")

router = APIRouter()


# ---------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------

class StartCallsBody(BaseModel):
    limit: Optional[int] = Field(default=None, ge=0)


class WebCallInitBody(BaseModel):
    client_id: Optional[int] = None


class WebCallStartedBody(BaseModel):
    vapi_call_id: Optional[str] = None


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _create_call_row(db: Session, client: Client) -> Call:
    """Insert a new pending Call row for a given client."""
    call = Call(client_id=client.id, status="pending", started_at=datetime.utcnow())
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def _initiate_call_for_client(db: Session, client: Client) -> dict:
    """Start one outbound Vapi call and update the Call row."""
    call = _create_call_row(db, client)
    try:
        vapi_response = start_outbound_call(client, local_call_id=call.id)
        vapi_call_id = vapi_response.get("id") or vapi_response.get("callId")
        if not vapi_call_id:
            logger.warning(
                "Vapi response did not include a call id. Raw response: %s",
                vapi_response,
            )
        call.call_sid = vapi_call_id
        call.status = "initiated"
        db.commit()
        return {
            "client_id": client.id,
            "call_id": call.id,
            "call_sid": vapi_call_id,
            "vapi_call_id": vapi_call_id,
            "status": "initiated",
        }
    except Exception as exc:
        logger.exception("Failed to initiate Vapi call for client %s: %s", client.id, exc)
        call.status = "failed"
        call.summary = f"Failed to initiate: {exc}"
        call.ended_at = datetime.utcnow()
        db.commit()
        return {
            "client_id": client.id,
            "call_id": call.id,
            "status": "failed",
            "error": str(exc),
        }


# ---------------------------------------------------------------------
# Outbound phone-call endpoints
# ---------------------------------------------------------------------

@router.post("/start-calls")
def start_calls(
    body: StartCallsBody = StartCallsBody(),
    db: Session = Depends(get_db),
):
    """
    Start outbound calls for every client that has NOT yet been called
    successfully.

    Body (optional JSON):
        { "limit": 5 }   # cap number of calls per batch
    """
    limit = body.limit or None

    callable_clients = (
        db.query(Client).order_by(Client.created_at.asc()).all()
    )

    pending_clients = []
    for c in callable_clients:
        has_active = any(
            call.status in {"initiated", "answered", "in-progress", "completed"}
            for call in c.calls
        )
        if not has_active:
            pending_clients.append(c)

    if limit:
        pending_clients = pending_clients[:limit]

    if not pending_clients:
        return {
            "success": True,
            "message": "No pending clients to call.",
            "results": [],
        }

    results = [_initiate_call_for_client(db, c) for c in pending_clients]

    return {
        "success": True,
        "started": len([r for r in results if r["status"] == "initiated"]),
        "failed": len([r for r in results if r["status"] == "failed"]),
        "results": results,
    }


@router.post("/call/{client_id}")
def call_single_client(client_id: int, db: Session = Depends(get_db)):
    """Start an outbound call for ONE specific client."""
    client = db.get(Client, client_id)
    if not client:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Client not found."},
        )

    result = _initiate_call_for_client(db, client)
    status_code = 200 if result["status"] == "initiated" else 500
    return JSONResponse(
        status_code=status_code,
        content={"success": result["status"] == "initiated", "result": result},
    )


# ---------------------------------------------------------------------
# WEB CALL (in-browser) endpoints
# ---------------------------------------------------------------------
# A web call uses Vapi's Web SDK + the user's browser microphone, instead
# of dialing a real phone number. Free to test on any Vapi account, and
# perfect when free Vapi phone numbers can't dial your country.
# ---------------------------------------------------------------------


def _get_or_create_web_visitor(db: Session) -> Client:
    """Reuse a single 'Web Visitor' Client row for all in-browser tests."""
    placeholder_phone = "+10000000000"
    client = (
        db.query(Client)
        .filter_by(phone_number=placeholder_phone)
        .first()
    )
    if client:
        return client

    client = Client(
        name="Web Visitor",
        phone_number=placeholder_phone,
        company="(Web Test)",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.post("/web-call/init")
def web_call_init(
    body: WebCallInitBody = WebCallInitBody(),
    db: Session = Depends(get_db),
):
    """
    Prepare a new in-browser call.

    Body (optional JSON):
        { "client_id": 42 }   # use a specific lead; otherwise a Web Visitor is used

    Response:
        {
            "public_key": "...",       # Vapi public key for the Web SDK
            "assistant": { ... },      # inline assistant config (system prompt, model, voice)
            "local_call_id": 17,       # our DB row's id
            "client_id": 5
        }
    """
    if body.client_id:
        client = db.get(Client, body.client_id)
        if not client:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Client not found."},
            )
    else:
        client = _get_or_create_web_visitor(db)

    call = _create_call_row(db, client)
    assistant = build_web_call_payload(client, local_call_id=call.id)

    if not Config.VAPI_PUBLIC_KEY:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "VAPI_PUBLIC_KEY is not configured on the server.",
            },
        )

    return {
        "success": True,
        "public_key": Config.VAPI_PUBLIC_KEY,
        "assistant": assistant,
        "local_call_id": call.id,
        "client_id": client.id,
    }


@router.post("/web-call/{local_call_id}/started")
def web_call_started(
    local_call_id: int,
    body: WebCallStartedBody = WebCallStartedBody(),
    db: Session = Depends(get_db),
):
    """
    The browser calls this once Vapi reports `call-start` so we can
    record Vapi's call id on our Call row and match incoming webhooks.

    Body: { "vapi_call_id": "<uuid>" }
    """
    call = db.get(Call, local_call_id)
    if not call:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Call not found."},
        )

    if body.vapi_call_id:
        call.call_sid = body.vapi_call_id
    call.status = "answered"
    db.commit()

    return {"success": True}
