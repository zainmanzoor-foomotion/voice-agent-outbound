"""
services/memory_service.py
--------------------------
Short-term conversational memory.

Strategy (per spec — no vector DB, no RAG):
- Pull the most recent N messages from the database for a given call.
- Return them in the chat format the Groq SDK expects:
      [{"role": "user"|"assistant", "content": "..."}]
"""

from typing import Dict, List

from sqlalchemy.orm import Session

from config import Config
from models import Message


def get_recent_history(
    db: Session,
    call_id: int,
    limit: int | None = None,
) -> List[Dict[str, str]]:
    """
    Return the last `limit` messages for a call in chronological order,
    formatted for the LLM chat API.
    """
    if limit is None:
        limit = Config.MEMORY_WINDOW

    # Get the most recent messages first, then re-sort ascending so the
    # LLM sees them in time order.
    rows = (
        db.query(Message)
        .filter_by(call_id=call_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()

    history: List[Dict[str, str]] = []
    for msg in rows:
        role = "assistant" if msg.speaker == "assistant" else "user"
        history.append({"role": role, "content": msg.content})

    return history


def add_message(
    db: Session,
    call_id: int,
    speaker: str,
    content: str,
) -> Message:
    """
    Persist a single conversational turn.

    `speaker` must be either "user" or "assistant".
    """
    if speaker not in {"user", "assistant"}:
        raise ValueError(f"Invalid speaker: {speaker}")

    msg = Message(call_id=call_id, speaker=speaker, content=content)
    db.add(msg)
    db.commit()
    return msg
