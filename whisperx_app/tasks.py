"""Celery tasks — transcription pipeline."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from celery.utils.log import get_task_logger

from whisperx_app.celery_app import celery_app

logger = get_task_logger(__name__)

UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads"))
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/data/results"))


@celery_app.task(
    name="whisperx_app.tasks.transcribe_job",
    bind=True,
    max_retries=2,
    soft_time_limit=7200,  # 2 hours
)
def transcribe_job(self, job_id: str) -> dict:
    """Run WhisperX transcription for a job and persist the result."""
    return asyncio.run(_run(self, job_id))


async def _run(task, job_id: str) -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession
    from whisperx_app.api.db import AsyncSessionLocal, Job
    from whisperx_app.api.email_service import (
        send_transcription_done,
        send_transcription_error,
    )

    async with AsyncSessionLocal() as db:
        job: Job | None = await db.get(Job, job_id)
        if job is None:
            logger.error("Job %s not found", job_id)
            return {"error": "not found"}

        # Mark as processing
        job.status = "processing"
        await db.commit()

    audio_path = UPLOADS_DIR / job_id / "audio"
    if not audio_path.exists():
        await _fail(job_id, "Audiodatei nicht gefunden")
        return {"error": "file missing"}

    result_dir = RESULTS_DIR / job_id
    result_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, _transcribe_sync, job, str(audio_path)
        )
    except Exception as exc:
        logger.exception("Transcription failed for job %s", job_id)
        await _fail(job_id, str(exc))
        # Send error email if requested
        async with AsyncSessionLocal() as db:
            job = await db.get(Job, job_id)
            if job and job.notify_email:
                try:
                    await send_transcription_error(
                        job.notify_email, job.original_filename or job_id, job_id
                    )
                except Exception:
                    pass
        return {"error": str(exc)}

    # Save result
    ext = {"md": "md", "txt": "txt", "json": "json"}.get(job.output_format, "md")
    result_file = result_dir / f"transcript.{ext}"
    result_file.write_text(result, encoding="utf-8")

    # Update job as done
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        job.status = "done"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        notify_email = job.notify_email
        filename = job.original_filename or job_id
        fmt = job.output_format

    # Send success email
    if notify_email:
        try:
            await send_transcription_done(notify_email, filename, job_id, fmt)
        except Exception as exc:
            logger.warning("Could not send email for job %s: %s", job_id, exc)

    return {"status": "done", "job_id": job_id}


def _transcribe_sync(job, audio_path: str) -> str:
    """Run WhisperX synchronously (called in executor thread)."""
    import whisperx
    from whisperx_app.formatter import format_result

    device = "cuda" if _has_cuda() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    batch_size = 16 if device == "cuda" else 4

    logger.info("Loading model %s on %s", job.model, device)
    model = whisperx.load_model(job.model, device, compute_type=compute_type)

    logger.info("Transcribing %s", audio_path)
    raw = model.transcribe(audio_path, batch_size=batch_size, language=job.language or None)

    logger.info("Aligning")
    align_model, metadata = whisperx.load_align_model(
        language_code=raw["language"], device=device
    )
    raw = whisperx.align(raw["segments"], align_model, metadata, audio_path, device)

    if job.diarize:
        hf_token = _get_hf_token()
        if hf_token:
            logger.info("Diarizing")
            diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=hf_token, device=device
            )
            diarize_segments = diarize_model(audio_path)
            raw = whisperx.assign_word_speakers(diarize_segments, raw)

    return format_result(
        raw,
        fmt=job.output_format,
        source_file=job.original_filename or "audio",
        model_name=job.model,
        speaker_names={},
    )


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _get_hf_token() -> str | None:
    try:
        from whisperx_app.config import load_config
        return load_config().hf_token
    except Exception:
        return os.environ.get("HF_TOKEN")


async def _fail(job_id: str, error: str) -> None:
    from whisperx_app.api.db import AsyncSessionLocal, Job
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        if job:
            job.status = "error"
            job.error_message = error
            await db.commit()
