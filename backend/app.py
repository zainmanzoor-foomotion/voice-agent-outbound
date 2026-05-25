"""
app.py
------
FastAPI application entry point for the AI voice calling backend.

Run with:
    python app.py              # convenience wrapper around uvicorn
    uvicorn app:app --reload   # equivalent, more explicit

The app:
    1. Loads config from .env
    2. Creates the SQLite database (if missing) via the startup lifespan
    3. Registers all route routers
    4. Enables CORS so the React frontend on :5173 can talk to it
"""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import Config
from database import init_db
from routes.call_routes import router as call_router
from routes.dashboard_routes import router as dashboard_router
from routes.invite_routes import router as invite_router
from routes.upload_routes import router as upload_router
from routes.webhook_routes import router as webhook_router
from utils.logger import get_logger


logger = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run on startup: ensure directories exist + create DB tables."""
    Config.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    Path(Config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="AI Voice Calling Agent",
        description=(
            "Outbound AI phone-calling backend. Vapi handles telephony + "
            "STT + TTS, Groq runs the live LLM and post-call extraction."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Allow the React dev server (Vite, port 5173) to call this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers (formerly Flask blueprints).
    app.include_router(upload_router)
    app.include_router(call_router)
    app.include_router(webhook_router)
    app.include_router(dashboard_router)
    app.include_router(invite_router)

    # Health check.
    @app.get("/")
    def index():
        return {
            "service": "AI Voice Calling Agent",
            "status": "ok",
            "model": Config.GROQ_MODEL,
            "base_url": Config.BASE_URL or "(not set — start ngrok)",
        }

    # ----------------------------------------------------------------
    # Global error handlers
    # Keep the response shape compatible with the old Flask backend
    # so the React frontend doesn't need to change.
    # ----------------------------------------------------------------

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException):
        # Use {"error": "..."} so the frontend's existing handling works.
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail if isinstance(exc.detail, str) else "Error"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "Invalid request payload.", "details": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.exception("Server error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    # Listen on 0.0.0.0 so ngrok can tunnel into the container/host.
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=5000,
        reload=Config.DEBUG,
    )
