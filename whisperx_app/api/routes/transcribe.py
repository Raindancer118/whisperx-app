"""Transcription endpoints — submit audio jobs and poll results."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from whisperx_app.api.dependencies import require_scope
from whisperx_app.api.job_store import job_store
from whisperx_app.api.models import (
    JobCreatedResponse,
    JobStatusResponse,
    TokenPayload,
)
from whisperx_app.config import load_config
from whisperx_app.estimator import estimate_processing_time, get_audio_duration
from whisperx_app.gpu import detect_hardware

router = APIRouter(prefix="/api/v1", tags=["transcription"])


@router.post(
    "/transcribe",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_transcription(
    audio_file: UploadFile = File(..., description="Audio or video file"),
    model: str = Form("large-v3"),
    device: str = Form("auto"),
    format: str = Form("md"),
    diarize: bool = Form(True),
    speaker_names: Optional[str] = Form(None, description='JSON: {"SPEAKER_00": "Tom"}'),
    language: Optional[str] = Form(None),
    user: TokenPayload = Depends(require_scope("transcribe")),
) -> JobCreatedResponse:
    """Submit an audio file for transcription. Returns a job ID for polling."""
    import json as _json

    # Validate format
    if format not in ("txt", "json", "md"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültiges Format: {format!r}. Erlaubt: txt, json, md",
        )

    # Parse speaker names
    parsed_speaker_names: Optional[dict] = None
    if speaker_names:
        try:
            parsed_speaker_names = _json.loads(speaker_names)
        except _json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="speaker_names muss ein valides JSON-Objekt sein",
            )

    # Resolve device
    cfg = load_config()
    hw = detect_hardware()
    if device == "auto":
        resolved_device = "cuda" if hw["cuda"] else "cpu"
    else:
        resolved_device = device

    compute_type = "float16" if resolved_device == "cuda" else "int8"
    batch_size = cfg.api_batch_size_gpu if resolved_device == "cuda" else cfg.api_batch_size_cpu

    audio_bytes = await audio_file.read()

    # Estimate processing time
    estimated_seconds: Optional[float] = None
    try:
        import tempfile, pathlib
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = pathlib.Path(tmp.name)
        duration = get_audio_duration(tmp_path)
        tmp_path.unlink(missing_ok=True)
        if duration:
            estimated_seconds = estimate_processing_time(
                duration, resolved_device, model,
                gpu_device_name=hw.get("device_name"),
                diarize=diarize,
            )
    except Exception:
        pass

    # Enqueue job
    hf_token = cfg.hf_token if diarize else None
    params = {
        "model": model,
        "device": resolved_device,
        "compute_type": compute_type,
        "diarize": diarize,
        "hf_token": hf_token,
        "language": language,
        "batch_size": batch_size,
        "speaker_names": parsed_speaker_names,
    }
    job = job_store.create_job(fmt=format, params=params, audio_bytes=audio_bytes)

    return JobCreatedResponse(
        job_id=job.job_id,
        status=job.status,
        estimated_seconds=estimated_seconds,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    user: TokenPayload = Depends(require_scope("transcribe")),
) -> JobStatusResponse:
    """Poll job status and retrieve result when complete."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id!r} nicht gefunden",
        )
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        format=job.format,
        result=job.result,
        segments=job.segments,
        error=job.error,
        progress_pct=job.progress_pct,
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    user: TokenPayload = Depends(require_scope("transcribe")),
) -> None:
    """Cancel or delete a job."""
    deleted = job_store.delete_job(job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id!r} nicht gefunden",
        )
