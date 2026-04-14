"""FastAPI application factory for WhisperX-App REST API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whisperx_app import __version__
from whisperx_app.api.job_store import job_store
from whisperx_app.api.routes import health, transcribe


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the background transcription worker."""
    job_store.start_worker()
    yield
    await job_store.stop_worker()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="WhisperX-App API",
        description=(
            "REST API for audio transcription with speaker diarization. "
            "Authentication via Volantic Auth (RS256 JWT)."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — adjust origins for your web project
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(transcribe.router)

    return app
