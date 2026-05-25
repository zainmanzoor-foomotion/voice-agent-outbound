"""
services/vapi_service.py
------------------------
Wrapper around the Vapi REST API.

Vapi handles the entire voice loop for us:
    telephony  +  speech-to-text  +  LLM (Groq)  +  text-to-speech

We just:
    1. Tell Vapi to dial a customer.
    2. Provide an "assistant" config (system prompt, first message,
       Groq model, voice, transcriber, server URL for webhooks).
    3. Receive a single webhook stream at our /vapi-webhook endpoint.

Docs: https://docs.vapi.ai/api-reference/calls/create
"""

from typing import Dict, Optional

import requests

from config import Config
from models import Client
from services.prompt_service import build_system_prompt, build_initial_greeting
from utils.logger import get_logger


logger = get_logger("vapi_service")


VAPI_BASE_URL = "https://api.vapi.ai"


def _auth_headers() -> Dict[str, str]:
    """Standard auth + JSON headers for Vapi REST calls."""
    if not Config.VAPI_PRIVATE_KEY:
        raise RuntimeError(
            "VAPI_PRIVATE_KEY is missing. Add it to your .env file."
        )
    return {
        "Authorization": f"Bearer {Config.VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json",
    }


def _build_assistant_config(client: Client) -> Dict:
    """
    Build the inline 'assistant' object Vapi expects for the call.

    Everything the AI needs is in here:
      - system prompt
      - opening line ("firstMessage")
      - Groq LLM + model
      - voice (TTS) + transcriber (STT)
      - serverUrl so Vapi sends events back to us
    """
    system_prompt = build_system_prompt(client)
    first_message = build_initial_greeting(client)

    assistant: Dict = {
        "name": Config.AGENT_NAME,
        "firstMessage": first_message,
        # When Vapi sees the user say one of these phrases, it hangs up.
        "endCallPhrases": [
            "goodbye",
            "have a good day",
            "have a great day",
            "talk later",
            "bye bye",
        ],
        # --- LLM (Groq) ---
        "model": {
            "provider": "groq",
            "model": Config.GROQ_MODEL,
            "temperature": 0.7,
            "maxTokens": 150,
            "messages": [
                {"role": "system", "content": system_prompt},
            ],
        },
        # --- Text-to-Speech (Vapi-bundled voice; no extra keys needed) ---
        "voice": {
            "provider": "vapi",
            "voiceId": "Elliot",
        },
        # --- Speech-to-Text ---
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
        },
        # --- Voicemail handling ---
        # If the call hits an answering machine, Vapi detects it within a
        # few seconds, plays a short voicemail message, and hangs up. Without
        # this the AI will try to "talk to" the voicemail greeting, which
        # results in nonsense transcripts (e.g. the voicemail reading out
        # the phone number being picked up as user speech).
        "voicemailDetection": {
            "provider": "vapi",
            "enabled": True,
            "backoffPlan": {
                "startAtSeconds": 5,
                "frequencySeconds": 5,
                "maxRetries": 6,
            },
        },
        "voicemailMessage": (
            f"Hi, this is {Config.AGENT_NAME} from {Config.BUSINESS_NAME}. "
            f"We wanted to chat with you about {Config.BUSINESS_SERVICE}. "
            "We'll try again later. Have a great day!"
        ),
        # If the call sits silent for this long, hang up gracefully.
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,  # safety cap: 10 minutes
        # Stop listening if the human side hasn't said anything sensible
        # at the start (catches voicemail / IVR menus the detector missed).
        "endCallFunctionEnabled": True,
        # --- Where Vapi sends webhook events ---
        "serverMessages": [
            "status-update",
            "end-of-call-report",
            "transcript",
        ],
    }

    # Per-call server URL is set on the *call* object below, not the assistant,
    # so a single assistant config works for every client.
    return assistant


def build_web_call_payload(client: Client, local_call_id: int) -> Dict:
    """
    Build the assistant config the frontend needs to start a Vapi WEB call.

    A web call runs in the browser via the Vapi Web SDK and uses the
    listener's microphone/speakers — no real phone number, no telephony
    cost. Free to test on any Vapi account.

    The shape returned here is consumed by `vapi.start(assistant)` on the
    frontend. We also include `serverUrl` so webhooks (transcripts, end-of-
    call-report) flow back into our DB exactly like a phone call.
    """
    assistant = _build_assistant_config(client)

    # serverUrl is normally set via assistantOverrides on phone calls;
    # for web calls we include it directly inside the assistant config.
    assistant["serverUrl"] = f"{Config.BASE_URL}/vapi-webhook"
    if Config.VAPI_WEBHOOK_SECRET:
        assistant["serverUrlSecret"] = Config.VAPI_WEBHOOK_SECRET

    # Tag the call with our internal IDs so the webhook can find the
    # right Call row even before we know Vapi's call.id.
    assistant["metadata"] = {
        "local_call_id": local_call_id,
        "client_id": client.id,
    }
    return assistant


def start_outbound_call(client: Client, local_call_id: int) -> Dict:
    """
    Place an outbound call via Vapi.

    Parameters
    ----------
    client : Client
        The lead we're calling.
    local_call_id : int
        Our internal Call row id. We embed this in the call's metadata so
        every incoming webhook can be matched back to the right Call,
        even before we know Vapi's call.id.

    Returns
    -------
    dict
        Vapi's full JSON response. The Vapi call id is in `response["id"]`.
    """
    if not Config.BASE_URL:
        raise RuntimeError(
            "BASE_URL is not set. Start ngrok and put the https URL in your .env."
        )
    if not Config.VAPI_PHONE_NUMBER_ID:
        raise RuntimeError(
            "VAPI_PHONE_NUMBER_ID is missing. Get a phone number id from the "
            "Vapi dashboard (Phone Numbers section) and add it to your .env."
        )

    payload = {
        "phoneNumberId": Config.VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": client.phone_number,
            "name": client.name or "",
        },
        "assistant": _build_assistant_config(client),
        # Per-call server URL — Vapi POSTs every webhook event here.
        "assistantOverrides": {
            "serverUrl": f"{Config.BASE_URL}/vapi-webhook",
        },
        # Call-level metadata — Vapi echoes this back on every webhook,
        # so we can match webhooks to our Call row even if `call_sid`
        # somehow didn't get saved.
        "metadata": {
            "local_call_id": local_call_id,
            "client_id": client.id,
        },
    }

    # If a webhook secret is configured, Vapi will echo it back on every
    # webhook in the `X-Vapi-Secret` header so we can verify it.
    if Config.VAPI_WEBHOOK_SECRET:
        payload["assistantOverrides"]["serverUrlSecret"] = Config.VAPI_WEBHOOK_SECRET

    logger.info(
        "Placing Vapi call to %s (client_id=%s, local_call_id=%s)",
        client.phone_number, client.id, local_call_id,
    )

    try:
        response = requests.post(
            f"{VAPI_BASE_URL}/call/phone",
            headers=_auth_headers(),
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.exception("Network error calling Vapi: %s", exc)
        raise RuntimeError(f"Network error contacting Vapi: {exc}") from exc

    if response.status_code >= 400:
        # Surface Vapi's error body so debugging is painless.
        logger.error(
            "Vapi call creation failed (%s): %s",
            response.status_code, response.text,
        )
        raise RuntimeError(
            f"Vapi returned {response.status_code}: {response.text}"
        )

    data = response.json()

    # Vapi sometimes wraps the call in a top-level field; normalize so
    # callers can always do response["id"].
    if isinstance(data, list) and data:
        data = data[0]

    logger.info(
        "Vapi accepted call: id=%s status=%s (local_call_id=%s)",
        data.get("id"), data.get("status"), local_call_id,
    )
    return data


def fetch_call(call_id: str) -> Optional[Dict]:
    """
    Fetch a single call's record from Vapi.

    Useful for backfilling transcripts / status if a webhook was missed.
    """
    if not call_id:
        return None
    try:
        response = requests.get(
            f"{VAPI_BASE_URL}/call/{call_id}",
            headers=_auth_headers(),
            timeout=15,
        )
        if response.status_code == 200:
            return response.json()
        logger.warning("Vapi fetch_call(%s) returned %s", call_id, response.status_code)
    except requests.RequestException as exc:
        logger.warning("Vapi fetch_call(%s) network error: %s", call_id, exc)
    return None
