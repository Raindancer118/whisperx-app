"""Pydantic request and response models for the WhisperX-App REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TokenPayload(BaseModel):
    sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    scope: str = ""
    exp: Optional[int] = None
    iss: Optional[str] = None
    aud: Optional[str | list[str]] = None
    jti: Optional[str] = None


# ---------------------------------------------------------------------------
# Transcription job
# ---------------------------------------------------------------------------

class JobStatus(str):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranscribeRequest(BaseModel):
    model: str = Field("large-v3", description="WhisperX model identifier")
    device: str = Field("auto", description="Compute device: auto, cpu, or cuda")
    format: str = Field("md", description="Output format: txt, json, or md")
    diarize: bool = Field(True, description="Enable speaker diarization")
    speaker_names: Optional[dict[str, str]] = Field(
        None, description='Speaker name mapping, e.g. {"SPEAKER_00": "Tom"}'
    )
    language: Optional[str] = Field(None, description="ISO language code, or null for auto-detect")


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str
    estimated_seconds: Optional[float] = None
    message: str = "Job queued"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    format: Optional[str] = None
    result: Optional[str] = None
    segments: Optional[list[dict[str, Any]]] = None
    error: Optional[str] = None
    progress_pct: Optional[int] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    available_models: list[str]
