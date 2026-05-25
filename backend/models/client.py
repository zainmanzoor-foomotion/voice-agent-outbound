"""
models/client.py
----------------
Client model: represents one person/lead the AI agent will call.
"""

import json
import secrets
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session, relationship

from database import Base


class Client(Base):
    """A lead/contact uploaded by the admin via CSV/XLSX."""

    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)

    # Basic contact info (from uploaded file).
    name = Column(String(150), nullable=True)
    phone_number = Column(String(32), nullable=False, index=True)
    company = Column(String(150), nullable=True)
    email = Column(String(150), nullable=True)

    # Filled in by the AI as the conversation progresses.
    interest_level = Column(String(20), default="unknown")  # high|medium|low|unknown
    notes = Column(Text, nullable=True)

    # Structured JSON string of extracted info (budget, callback time, etc.)
    extracted_information = Column(Text, default="{}")

    # Random URL-safe token used to build a public "click-to-talk" link
    # we send the client over WhatsApp. Nullable so existing rows still work;
    # `get_or_create_invite_token()` lazily fills it in.
    invite_token = Column(String(64), unique=True, nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # One client can be called many times.
    calls = relationship(
        "Call",
        backref="client",
        lazy="select",
        cascade="all, delete-orphan",
    )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def get_extracted_information(self) -> dict:
        """Safely parse the JSON blob stored in extracted_information."""
        try:
            return json.loads(self.extracted_information or "{}")
        except (ValueError, TypeError):
            return {}

    def set_extracted_information(self, data: dict) -> None:
        """Serialize a dict into the JSON column."""
        self.extracted_information = json.dumps(data or {})

    def get_or_create_invite_token(self, db: Session) -> str:
        """Lazily generate a URL-safe invite token for this client."""
        if not self.invite_token:
            self.invite_token = secrets.token_urlsafe(16)
            db.commit()
        return self.invite_token

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation for the API."""
        return {
            "id": self.id,
            "name": self.name,
            "phone_number": self.phone_number,
            "company": self.company,
            "email": self.email,
            "interest_level": self.interest_level,
            "notes": self.notes,
            "extracted_information": self.get_extracted_information(),
            "invite_token": self.invite_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "total_calls": len(self.calls),
        }
