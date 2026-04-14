"""Health check endpoint — no authentication required."""

from fastapi import APIRouter

from whisperx_app import __version__
from whisperx_app.api.models import HealthResponse
from whisperx_app.model_manager import list_available_models

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Liveness check. Returns version and locally cached model names."""
    return HealthResponse(
        status="ok",
        version=__version__,
        available_models=list_available_models(),
    )
