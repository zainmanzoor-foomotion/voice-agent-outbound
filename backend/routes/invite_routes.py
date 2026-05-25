"""
routes/invite_routes.py
-----------------------
"Click-to-talk" outbound flow over WhatsApp.

Idea:
  - For each client we generate a unique invite token.
  - We build a wa.me URL with a pre-filled message containing
    https://<our-app>/talk/<token>.
  - Admin opens the wa.me URL (one click), WhatsApp Web opens with the
    message pre-filled, admin hits send.
  - Client receives the WhatsApp message, taps the link, and lands on
    the public /talk/<token> page where they tap "Start Call" and speak
    to our AI agent (Vapi Web SDK in their browser).
  - Transcripts/extraction/summary flow into our DB exactly like
    a phone or dashboard web call.

No telephony costs. No WhatsApp Business API. Just standard wa.me deep links.
"""

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config import Config
from database import get_db
from models import Call, Client
from services.vapi_service import build_web_call_payload
from utils.helpers import normalize_phone_number


router = APIRouter()


# Jinja2 templates live in backend/templates/ (same place Flask was reading
# them from). Jinja2Templates wants a directory string/path.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------
# Admin endpoints (called by the React dashboard)
# ---------------------------------------------------------------------

@router.get("/invitations/{client_id}")
def get_invitation(client_id: int, db: Session = Depends(get_db)):
    """
    Build the WhatsApp deep-link + the talk URL for a single client.

    Response:
        {
            "client_id": 1,
            "phone_number": "+923256317223",
            "name": "Maaz",
            "talk_url": "https://abc.ngrok-free.dev/talk/Xyz123",
            "whatsapp_url": "https://wa.me/923256317223?text=..."
        }

    Admin opens `whatsapp_url` in a new tab — WhatsApp Web takes over,
    message pre-filled, one click to send.
    """
    client = db.get(Client, client_id)
    if not client:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Client not found."},
        )

    token = client.get_or_create_invite_token(db)
    talk_url = _build_talk_url(token)
    whatsapp_url = _build_whatsapp_url(client, talk_url)

    return {
        "client_id": client.id,
        "name": client.name,
        "phone_number": client.phone_number,
        "talk_url": talk_url,
        "whatsapp_url": whatsapp_url,
    }


# ---------------------------------------------------------------------
# Public HTML landing page (what the client sees when they tap the link)
# ---------------------------------------------------------------------

@router.get("/talk/{token}")
def talk_page(token: str, request: Request, db: Session = Depends(get_db)):
    """
    Render the customer-facing "tap to talk" page.

    This is a single self-contained HTML page (Tailwind + Vapi Web SDK
    loaded from CDN) so the customer can land here directly via the
    public ngrok URL — no React build needed.
    """
    client = db.query(Client).filter_by(invite_token=token).first()
    if not client:
        return templates.TemplateResponse(
            request,
            "talk.html",
            {
                "token": token,
                "first_name": "",
                "business_name": "Unknown",
                "agent_name": "",
                "business_service": "this link is no longer valid",
            },
            status_code=404,
        )

    first_name = (client.name or "").split()[0] if client.name else ""

    return templates.TemplateResponse(
        request,
        "talk.html",
        {
            "token": token,
            "first_name": first_name,
            "business_name": Config.BUSINESS_NAME,
            "agent_name": Config.AGENT_NAME,
            "business_service": Config.BUSINESS_SERVICE,
        },
    )


# ---------------------------------------------------------------------
# Public JSON endpoints (called by the talk page's JavaScript)
# ---------------------------------------------------------------------

@router.get("/invite/{token}")
def invite_landing(token: str, db: Session = Depends(get_db)):
    """
    Public: return the data the /talk/<token> landing page needs to render.

    No auth, no PII beyond the client's first name + business identity.
    """
    client = db.query(Client).filter_by(invite_token=token).first()
    if not client:
        return JSONResponse(
            status_code=404,
            content={"error": "Invalid or expired link."},
        )

    first_name = (client.name or "").split()[0] if client.name else ""

    return {
        "first_name": first_name,
        "business_name": Config.BUSINESS_NAME,
        "agent_name": Config.AGENT_NAME,
        "business_service": Config.BUSINESS_SERVICE,
    }


@router.post("/invite/{token}/start")
def invite_start(token: str, db: Session = Depends(get_db)):
    """
    Public: prepare a new in-browser Vapi call for the client that owns
    this invite token. Mirrors /web-call/init but doesn't require knowing
    the internal client_id.
    """
    client = db.query(Client).filter_by(invite_token=token).first()
    if not client:
        return JSONResponse(
            status_code=404,
            content={"error": "Invalid or expired link."},
        )

    if not Config.VAPI_PUBLIC_KEY:
        return JSONResponse(
            status_code=500,
            content={"error": "Server is missing VAPI_PUBLIC_KEY."},
        )

    # Reuse the /call-row creation pattern.
    call = Call(client_id=client.id, status="pending")
    db.add(call)
    db.commit()
    db.refresh(call)

    assistant = build_web_call_payload(client, local_call_id=call.id)

    return {
        "success": True,
        "public_key": Config.VAPI_PUBLIC_KEY,
        "assistant": assistant,
        "local_call_id": call.id,
    }


# ---------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------

def _build_talk_url(token: str) -> str:
    """
    Public link the client taps from WhatsApp.

    FastAPI itself serves /talk/<token> (see `talk_page` above), so we
    just point at the public ngrok URL. The customer's phone reaches it
    directly — no second tunnel needed for the React app.
    """
    base = Config.BASE_URL or "http://localhost:5000"
    return f"{base}/talk/{token}"


def _build_whatsapp_url(client: Client, talk_url: str) -> str:
    """
    Build a wa.me deep link with a pre-filled message.

    Format: https://wa.me/<international_number_without_plus>?text=<urlencoded>
    """
    phone_digits = normalize_phone_number(client.phone_number) or client.phone_number
    phone_digits = phone_digits.lstrip("+")

    first_name = (client.name or "").split()[0] if client.name else "there"

    message = (
        f"Hi {first_name}, this is {Config.AGENT_NAME} from "
        f"{Config.BUSINESS_NAME}. We help with {Config.BUSINESS_SERVICE}. "
        f"Tap below to have a quick voice chat with our AI assistant — "
        f"no app needed:\n\n{talk_url}"
    )

    return f"https://wa.me/{phone_digits}?text={quote(message)}"
