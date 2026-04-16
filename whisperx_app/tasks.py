"""Celery tasks — transcription pipeline."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from celery.utils.log import get_task_logger

from whisperx_app.celery_app import celery_app

logger = get_task_logger(__name__)

UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads"))
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/data/results"))

# Redis key / TTL for stream results
_STREAM_RESULT_TTL = 7 * 24 * 3600  # 7 days


def _stream_result_key(session_id: str) -> str:
    return f"whisperx:stream:result:{session_id}"


# =========================================================================== #
# Existing transcription job task                                              #
# =========================================================================== #

@celery_app.task(
    name="whisperx_app.tasks.transcribe_job",
    bind=True,
    max_retries=2,
    soft_time_limit=7200,
)
def transcribe_job(self, job_id: str) -> dict:
    """Run WhisperX transcription for a job and persist the result."""
    return asyncio.run(_run_job(self, job_id))


async def _run_job(task, job_id: str) -> dict:
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
        job.status = "processing"
        await db.commit()

    audio_path = UPLOADS_DIR / job_id / "audio"
    if not audio_path.exists():
        await _fail_job(job_id, "Audiodatei nicht gefunden")
        return {"error": "file missing"}

    result_dir = RESULTS_DIR / job_id
    result_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, _transcribe_sync, job, str(audio_path)
        )
    except Exception as exc:
        logger.exception("Transcription failed for job %s", job_id)
        await _fail_job(job_id, str(exc))
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

    ext = {"md": "md", "txt": "txt", "json": "json"}.get(job.output_format, "md")
    result_file = result_dir / f"transcript.{ext}"
    result_file.write_text(result, encoding="utf-8")

    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        job.status = "done"
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        notify_email = job.notify_email
        filename = job.original_filename or job_id
        fmt = job.output_format

    if notify_email:
        try:
            await send_transcription_done(notify_email, filename, job_id, fmt)
        except Exception as exc:
            logger.warning("Could not send email for job %s: %s", job_id, exc)

    return {"status": "done", "job_id": job_id}


# =========================================================================== #
# Live stream processing task                                                  #
# =========================================================================== #

@celery_app.task(
    name="whisperx_app.tasks.process_stream_task",
    bind=True,
    max_retries=0,
    soft_time_limit=86400,   # 24 h ceiling
)
def process_stream_task(
    self,
    session_id: str,
    audio_raw_path: str,
    audio_format: str,
    sample_rate: int,
    channels: int,
) -> dict:
    """Full post-processing pipeline for a completed live stream.

    Steps:
      1. Convert raw audio → 16 kHz mono WAV (ffmpeg)
      2. WhisperX transcription + alignment + diarization
      3. Gemma 4 correction pass (chunk-by-chunk via Ollama)
      4. Gemma 4 summary (via Ollama)
      5. Persist result in Redis; clean up audio files
    """
    return asyncio.run(
        _run_stream(session_id, audio_raw_path, audio_format, sample_rate, channels)
    )


async def _run_stream(
    session_id: str,
    audio_raw_path: str,
    audio_format: str,
    sample_rate: int,
    channels: int,
) -> dict:
    raw_path = Path(audio_raw_path)
    work_dir = raw_path.parent
    full_wav = work_dir / "full.wav"

    async def _store_result(payload: dict) -> None:
        """Persist result dict in Redis with TTL."""
        try:
            from whisperx_app.api import session_store
            await session_store.set(
                _stream_result_key(session_id),
                json.dumps(payload),
                ttl=_STREAM_RESULT_TTL,
            )
        except Exception as exc:
            logger.error("Could not store stream result in Redis: %s", exc)

    logger.info("[stream %s] Starting post-processing pipeline", session_id)

    # ── Step 1: Convert raw audio ──────────────────────────────────────── #
    try:
        logger.info("[stream %s] Converting audio…", session_id)
        await _convert_audio(raw_path, full_wav, audio_format, sample_rate, channels)
    except Exception as exc:
        msg = f"Audio conversion failed: {exc}"
        logger.error("[stream %s] %s", session_id, msg)
        await _store_result({"status": "failed", "error": msg})
        return {"error": msg}

    # ── Step 2: WhisperX transcription ────────────────────────────────── #
    try:
        logger.info("[stream %s] Running WhisperX…", session_id)
        final_transcript = await asyncio.get_event_loop().run_in_executor(
            None, _full_transcribe, full_wav
        )
    except Exception as exc:
        msg = f"WhisperX transcription failed: {exc}"
        logger.error("[stream %s] %s", session_id, msg)
        await _store_result({"status": "failed", "error": msg})
        return {"error": msg}
    finally:
        full_wav.unlink(missing_ok=True)

    # ── Step 3: Gemma correction pass ─────────────────────────────────── #
    try:
        logger.info("[stream %s] Running Gemma correction pass…", session_id)
        corrected = await _correction_pass(final_transcript)
    except Exception as exc:
        logger.warning(
            "[stream %s] Gemma correction failed (%s) — using raw transcript", session_id, exc
        )
        corrected = final_transcript   # degrade gracefully

    # ── Step 4: Gemma summary ─────────────────────────────────────────── #
    try:
        logger.info("[stream %s] Generating summary…", session_id)
        from whisperx_app.api.ollama_client import generate_summary
        summary = await generate_summary(corrected)
    except Exception as exc:
        logger.warning("[stream %s] Summary generation failed: %s", session_id, exc)
        summary = None

    # ── Step 5: Persist result ────────────────────────────────────────── #
    result = {
        "status": "done",
        "transcript": corrected,
        "summary": summary,
    }
    await _store_result(result)

    # Clean up raw audio (large file, no longer needed)
    raw_path.unlink(missing_ok=True)

    logger.info("[stream %s] Pipeline complete.", session_id)
    return result


# =========================================================================== #
# Internal helpers                                                             #
# =========================================================================== #

async def _convert_audio(
    src: Path, dst: Path, fmt: str, sample_rate: int, channels: int
) -> None:
    input_args = (["-f", "s16le", "-ar", str(sample_rate), "-ac", str(channels)]
                  if fmt == "pcm_s16le" else [])
    cmd = [
        "ffmpeg", "-y", *input_args, "-i", str(src),
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(dst),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace")[:400])


def _full_transcribe(wav_path: Path) -> str:
    from whisperx_app.config import load_config
    from whisperx_app.formatter import format_result
    from whisperx_app.gpu import detect_hardware
    from whisperx_app.transcriber import transcribe

    cfg = load_config()
    hw = detect_hardware()
    device = "cuda" if hw["cuda"] else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    batch_size = cfg.api_batch_size_gpu if device == "cuda" else cfg.api_batch_size_cpu

    result = transcribe(
        audio_path=wav_path,
        model_name=cfg.default_model,
        device=device,
        compute_type=compute_type,
        hf_token=cfg.hf_token,
        diarize=True,
        language=None,
        batch_size=batch_size,
    )
    return format_result(result=result, fmt="md", model_name=cfg.default_model)


async def _correction_pass(transcript: str) -> str:
    from whisperx_app.api.ollama_client import correct_transcript_chunk
    from whisperx_app.api.stream_processor import _CHUNK_SIZE
    from whisperx_app.api.text_utils import split_at_paragraphs

    if len(transcript) <= _CHUNK_SIZE:
        return await correct_transcript_chunk(chunk=transcript)

    chunks = split_at_paragraphs(transcript, _CHUNK_SIZE)
    corrected: list[str] = []
    _CTX = 500

    for i, chunk in enumerate(chunks):
        prev = chunks[i - 1][-_CTX:] if i > 0 else ""
        nxt = chunks[i + 1][:_CTX] if i < len(chunks) - 1 else ""
        corrected.append(await correct_transcript_chunk(
            chunk=chunk, prev_context=prev, next_context=nxt
        ))
        logger.debug("[correction] chunk %d/%d done", i + 1, len(chunks))

    return "\n\n".join(corrected)


def _transcribe_sync(job, audio_path: str) -> str:
    """Run WhisperX synchronously (called in executor thread) — existing jobs."""
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


async def _fail_job(job_id: str, error: str) -> None:
    from whisperx_app.api.db import AsyncSessionLocal, Job
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        if job:
            job.status = "error"
            job.error_message = error
            await db.commit()
