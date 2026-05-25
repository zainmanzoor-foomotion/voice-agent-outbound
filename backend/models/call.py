"""
models/call.py
--------------
Call model: one outbound call placed to a client.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


# Allowed status values for a call.
CALL_STATUSES = {
    "pending",
    "initiated",
    "answered",
    "in-progress",
    "completed",
    "failed",
    "no_answer",
}


class Call(Base):
    """Represents a single outbound call (via Vapi) to one client."""

    __tablename__ = "calls"

    id = Column(Integer, primary_key=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    # Vapi's unique call id (set after the call is initiated).
    call_sid = Column(String(64), unique=True, nullable=True, index=True)

    status = Column(String(20), default="pending")

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # AI-generated short summary of what happened on the call.
    summary = Column(Text, nullable=True)

    # One call has many messages (transcript turns).
    messages = relationship(
        "Message",
        backref="call",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="Message.timestamp.asc()",
    )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    @property
    def duration_seconds(self) -> int | None:
        """Return call duration in seconds, or None if not finished."""
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds())
        return None

    def to_dict(self, include_messages: bool = False) -> dict:
        data = {
            "id": self.id,
            "client_id": self.client_id,
            "client_name": self.client.name if self.client else None,
            "client_phone": self.client.phone_number if self.client else None,
            "call_sid": self.call_sid,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary,
            "message_count": len(self.messages),
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        return data
