"""
models/message.py
-----------------
Message model: one turn in a call's transcript.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from database import Base


class Message(Base):
    """A single conversational turn within a call."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)

    # Either "user" (the human on the phone) or "assistant" (the AI).
    speaker = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)

    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "call_id": self.call_id,
            "speaker": self.speaker,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
