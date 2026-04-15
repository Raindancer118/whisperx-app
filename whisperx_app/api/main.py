"""FastAPI application factory for WhisperX-App REST API + Web API."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whisperx_app import __version__
from whisperx_app.api.job_store import job_store
from whisperx_app.api.routes import health, transcribe
from whisperx_app.api.routes.web_auth import router as web_auth_router
from whisperx_app.api.routes.web_jobs import router as web_jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, start in-process worker. Shutdown: cleanup."""
    # Init database tables
    try:
        from whisperx_app.api.db import init_db
        await init_db()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("DB init failed (no DB in dev?): %s", exc)

    job_store.start_worker()
    yield
    await job_store.stop_worker()

    # Close Redis connection
    try:
        from whisperx_app.api import session_store
        await session_store.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="WhisperX-App",
        description="Audio-Transkription mit Sprecher-Diarisierung",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Existing REST API (Bearer JWT)
    app.include_router(health.router)
    app.include_router(transcribe.router)

    # Web API (session cookie)
    app.include_router(web_auth_router)
    app.include_router(web_jobs_router)

    return app
