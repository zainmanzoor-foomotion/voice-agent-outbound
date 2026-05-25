"""
routes/dashboard_routes.py
--------------------------
Read-only endpoints used by the React dashboard.

GET /clients
GET /clients/<id>
DELETE /clients/<id>
GET /calls
GET /calls/<id>
GET /transcripts/<call_id>
GET /dashboard/stats
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Call, Client, Message  # noqa: F401  (Message kept for symmetry)


router = APIRouter()


# ---------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------

@router.get("/clients")
def list_clients(
    search: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """List all clients. Supports ?search=<text> on name/company/phone."""
    search = (search or "").strip()
    query = db.query(Client)

    if search:
        like = f"%{search}%"
        query = query.filter(
            (Client.name.ilike(like))
            | (Client.phone_number.ilike(like))
            | (Client.company.ilike(like))
            | (Client.email.ilike(like))
        )

    clients = query.order_by(Client.created_at.desc()).all()
    return {"clients": [c.to_dict() for c in clients]}


@router.get("/clients/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db)):
    """Return one client plus a short list of their recent calls."""
    client = db.get(Client, client_id)
    if not client:
        return JSONResponse(status_code=404, content={"error": "Client not found."})

    data = client.to_dict()
    data["calls"] = [
        c.to_dict()
        for c in sorted(client.calls, key=lambda x: x.started_at, reverse=True)
    ]
    return data


@router.delete("/clients/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    """Delete one client (and all their calls + messages via cascade)."""
    client = db.get(Client, client_id)
    if not client:
        return JSONResponse(status_code=404, content={"error": "Client not found."})

    db.delete(client)
    db.commit()
    return {"success": True}


# ---------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------

@router.get("/calls")
def list_calls(
    status: Optional[str] = Query(default=None),
    client_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    List calls, newest first.

    Supports filters:
        ?status=completed
        ?client_id=42
    """
    query = db.query(Call)
    if status:
        query = query.filter(Call.status == status)
    if client_id:
        query = query.filter(Call.client_id == client_id)

    calls = query.order_by(Call.started_at.desc()).all()
    return {"calls": [c.to_dict() for c in calls]}


@router.get("/calls/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)):
    """Return one call with full transcript."""
    call = db.get(Call, call_id)
    if not call:
        return JSONResponse(status_code=404, content={"error": "Call not found."})
    return call.to_dict(include_messages=True)


@router.get("/transcripts/{call_id}")
def get_transcript(call_id: int, db: Session = Depends(get_db)):
    """Return only the transcript (list of messages) for a call."""
    call = db.get(Call, call_id)
    if not call:
        return JSONResponse(status_code=404, content={"error": "Call not found."})

    return {
        "call_id": call.id,
        "client_id": call.client_id,
        "messages": [m.to_dict() for m in call.messages],
    }


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------

@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    """Return aggregate counters used by the dashboard cards."""
    total_clients = db.query(func.count(Client.id)).scalar() or 0
    total_calls = db.query(func.count(Call.id)).scalar() or 0

    completed_calls = (
        db.query(func.count(Call.id)).filter(Call.status == "completed").scalar() or 0
    )
    pending_calls = (
        db.query(func.count(Call.id))
        .filter(Call.status.in_(["pending", "initiated", "answered", "in-progress"]))
        .scalar() or 0
    )
    failed_calls = (
        db.query(func.count(Call.id))
        .filter(Call.status.in_(["failed", "no_answer"]))
        .scalar() or 0
    )

    interested = (
        db.query(func.count(Client.id))
        .filter(Client.interest_level == "high")
        .scalar() or 0
    )

    return {
        "total_clients": total_clients,
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "pending_calls": pending_calls,
        "failed_calls": failed_calls,
        "highly_interested_clients": interested,
    }
