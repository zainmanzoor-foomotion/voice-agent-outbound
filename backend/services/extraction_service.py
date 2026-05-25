"""
services/extraction_service.py
------------------------------
Extracts structured information about the client from the conversation
and merges it into Client.extracted_information.

Fields we try to extract:
    - interest_level     ("high" | "medium" | "low" | "unknown")
    - callback_requested (bool)
    - callback_time      (string, free-form)
    - budget             (string, free-form)
    - business_needs     (string, short summary)
    - objections         (string, short summary)
    - follow_up          (string, requested follow-up action)

We use the LLM in JSON mode for robust structured extraction.
"""

import json
from typing import Dict, List

from groq import Groq
from sqlalchemy.orm import Session

from config import Config
from models import Client
from utils.logger import get_logger


logger = get_logger("extraction_service")


_groq_client: Groq | None = None
if Config.GROQ_API_KEY:
    try:
        _groq_client = Groq(api_key=Config.GROQ_API_KEY)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to init Groq client for extraction: %s", exc)


_EXTRACTION_SYSTEM_PROMPT = """You are an information extractor for sales call transcripts.

Read the conversation and output ONLY a valid JSON object with these keys:
{
  "interest_level": "high" | "medium" | "low" | "unknown",
  "callback_requested": true | false,
  "callback_time": "string or empty",
  "budget": "string or empty",
  "business_needs": "string or empty",
  "objections": "string or empty",
  "follow_up": "string or empty"
}

If a field is not mentioned, use "" (empty string) for strings, false for booleans,
and "unknown" for interest_level. Do not invent information. Return JSON only."""


def _empty_extraction() -> Dict:
    return {
        "interest_level": "unknown",
        "callback_requested": False,
        "callback_time": "",
        "budget": "",
        "business_needs": "",
        "objections": "",
        "follow_up": "",
    }


def extract_information(chat_history: List[Dict[str, str]]) -> Dict:
    """
    Run the LLM in JSON mode to extract structured info from the conversation.
    """
    if not chat_history:
        return _empty_extraction()

    if _groq_client is None:
        logger.warning("Groq not configured — skipping extraction.")
        return _empty_extraction()

    # Render the chat as a simple readable transcript for the extractor.
    transcript = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history
    )

    try:
        completion = _groq_client.chat.completions.create(
            model=Config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            temperature=0.0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Extraction returned invalid JSON. Falling back to empty.")
        return _empty_extraction()
    except Exception as exc:
        logger.exception("Extraction failed: %s", exc)
        return _empty_extraction()

    # Merge into the expected shape so missing keys do not blow up callers.
    merged = _empty_extraction()
    merged.update({k: v for k, v in data.items() if k in merged})
    return merged


def update_client_information(
    db: Session,
    client: Client,
    chat_history: List[Dict[str, str]],
) -> Dict:
    """
    Run extraction over the conversation and update the Client row in-place.

    Returns the new extracted info dict.
    """
    info = extract_information(chat_history)

    # Merge with whatever was already extracted so we keep prior signal.
    existing = client.get_extracted_information()
    existing.update({
        k: v
        for k, v in info.items()
        if v not in (None, "", "unknown", False) or k not in existing
    })

    client.set_extracted_information(existing)

    # Convenience: surface interest level on the client directly.
    if info.get("interest_level") and info["interest_level"] != "unknown":
        client.interest_level = info["interest_level"]

    db.commit()
    return existing
