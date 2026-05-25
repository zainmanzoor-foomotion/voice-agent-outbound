"""
database.py
-----------
SQLAlchemy setup for the FastAPI application.

We use plain SQLAlchemy (no Flask-SQLAlchemy) and expose:

- `engine`        : the SQLAlchemy Engine bound to our SQLite file.
- `SessionLocal`  : a sessionmaker factory; one Session per request.
- `Base`          : declarative base every model inherits from.
- `get_db()`      : a FastAPI dependency that yields a Session and
                    guarantees it is closed even on errors.
- `init_db()`     : called on app startup to create tables and apply
                    lightweight idempotent migrations.
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from config import Config
from utils.logger import get_logger


logger = get_logger("database")


Path(Config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)


# SQLite + threads: FastAPI runs sync endpoints in a thread pool, so the
# SQLite connection may be touched by different threads. `check_same_thread`
# disables SQLite's per-thread guard; our per-request Session pattern keeps
# usage safe.
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a per-request SQLAlchemy Session
    and always closes it afterwards.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create all tables (if missing) and apply tiny additive migrations.
    Called once from the FastAPI lifespan handler at startup.
    """
    # Importing the models package registers every model on Base.metadata.
    from models import Client, Call, Message  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_new_columns()
    logger.info("Database ready at %s", Config.DB_PATH)


def _ensure_new_columns() -> None:
    """
    Lightweight, idempotent column adds for SQLite.

    `Base.metadata.create_all()` only creates missing tables — it does NOT
    add new columns to existing tables. So when we add a new column to a
    model after the demo DB already exists, we add it here.
    """
    inspector = inspect(engine)
    if "clients" not in inspector.get_table_names():
        return

    existing_cols = {col["name"] for col in inspector.get_columns("clients")}
    statements: list[str] = []

    if "invite_token" not in existing_cols:
        statements.append(
            "ALTER TABLE clients ADD COLUMN invite_token VARCHAR(64)"
        )

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
            logger.info("Schema migrated: %s", stmt)
