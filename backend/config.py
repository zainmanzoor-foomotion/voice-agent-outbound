"""
config.py
---------
Central configuration object for the FastAPI application.

All runtime settings are loaded from environment variables (.env).
"""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Application configuration loaded from environment variables."""

    # --- App core ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    # APP_ENV is the canonical variable; FLASK_ENV is read for backward
    # compatibility with the old Flask-era .env files.
    ENV: str = os.getenv("APP_ENV") or os.getenv("FLASK_ENV", "development")
    DEBUG: bool = ENV != "production"

    # --- Database (SQLite + SQLAlchemy) ---
    DB_PATH = BASE_DIR / "database" / "app.db"
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{DB_PATH}"

    # --- File uploads ---
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    ALLOWED_UPLOAD_EXTENSIONS = {"csv", "xlsx"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # --- Vapi (voice platform: telephony + STT + LLM + TTS) ---
    # https://dashboard.vapi.ai
    VAPI_PRIVATE_KEY: str = os.getenv("VAPI_PRIVATE_KEY", "")
    VAPI_PUBLIC_KEY: str = os.getenv("VAPI_PUBLIC_KEY", "")
    VAPI_PHONE_NUMBER_ID: str = os.getenv("VAPI_PHONE_NUMBER_ID", "")
    # Optional: shared secret echoed back by Vapi on every webhook.
    VAPI_WEBHOOK_SECRET: str = os.getenv("VAPI_WEBHOOK_SECRET", "")

    # --- Groq LLM ---
    # Used both by Vapi (configured via API in vapi_service.py) AND by
    # our backend directly (for post-call extraction + summaries).
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # --- Public base URL exposed by ngrok ---
    # Vapi calls this URL for webhooks, so it MUST be reachable publicly.
    BASE_URL: str = os.getenv("BASE_URL", "").rstrip("/")

    # --- Business identity (used by prompt templates) ---
    BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "Acme AI Solutions")
    AGENT_NAME: str = os.getenv("AGENT_NAME", "Alex")
    BUSINESS_SERVICE: str = os.getenv(
        "BUSINESS_SERVICE", "AI-powered business automation tools"
    )

    # --- Conversation memory window for extraction ---
    MEMORY_WINDOW: int = 50
