"""Web API routes for job management and chunked file upload."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from whisperx_app.api.db import AsyncSession, Job, get_db
from fastapi import Depends
from whisperx_app.api.web_deps import WebUser

router = APIRouter(prefix="/api/web/jobs", tags=["web-jobs"])

UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads"))
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/data/results"))
CHUNK_TMP_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads"))


# ── Create job ──────────────────────────────────────────────────────────────

class CreateJobRequest(BaseModel):
    filename: str
    file_size: int
    total_chunks: int
    model: str = "large-v3"
    language: str | None = None
    output_format: str = "md"
    diarize: bool = True
    notify_email: str | None = None


@router.post("", status_code=201)
async def create_job(
    body: CreateJobRequest,
    user: WebUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = Job(
        id=str(uuid.uuid4()),
        user_id=user.user_id,
        user_email=user.email,
        notify_email=body.notify_email,
        original_filename=body.filename,
        file_size=body.file_size,
        model=body.model,
        language=body.language,
        output_format=body.output_format,
        diarize=body.diarize,
        total_chunks=body.total_chunks,
        received_chunks=0,
        status="uploading",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Create chunk storage directory
    (UPLOADS_DIR / job.id / "chunks").mkdir(parents=True, exist_ok=True)

    return job.to_dict()


# ── Upload chunk ────────────────────────────────────────────────────────────

@router.post("/{job_id}/chunks/{chunk_index}")
async def upload_chunk(
    job_id: str,
    chunk_index: int,
    user: WebUser,
    chunk: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job: Job | None = await db.get(Job, job_id)
    if not job or job.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job.status != "uploading":
        raise HTTPException(status_code=409, detail="Upload bereits abgeschlossen")

    chunk_path = UPLOADS_DIR / job_id / "chunks" / f"{chunk_index:06d}"
    with chunk_path.open("wb") as f:
        shutil.copyfileobj(chunk.file, f)

    job.received_chunks = chunk_index + 1
    await db.commit()

    # All chunks received → assemble file
    if job.received_chunks >= job.total_chunks:
        await _assemble_chunks(job, db)

    return {
        "received": job.received_chunks,
        "total": job.total_chunks,
        "status": job.status,
    }


async def _assemble_chunks(job: Job, db: AsyncSession) -> None:
    """Concatenate chunk files into the final audio file and queue the job."""
    chunks_dir = UPLOADS_DIR / job.id / "chunks"
    audio_path = UPLOADS_DIR / job.id / "audio"

    chunk_files = sorted(chunks_dir.glob("*"))
    with audio_path.open("wb") as out:
        for cf in chunk_files:
            with cf.open("rb") as inp:
                shutil.copyfileobj(inp, out)

    # Clean up chunk files
    shutil.rmtree(str(chunks_dir), ignore_errors=True)

    job.status = "queued"
    await db.commit()

    # Enqueue Celery task
    from whisperx_app.tasks import transcribe_job
    transcribe_job.apply_async(args=[job.id], queue="transcription")


# ── List user jobs ──────────────────────────────────────────────────────────

@router.get("")
async def list_jobs(
    user: WebUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=200),
) -> list[dict]:
    result = await db.execute(
        select(Job)
        .where(Job.user_id == user.user_id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    return [j.to_dict() for j in result.scalars().all()]


# ── Get single job ──────────────────────────────────────────────────────────

@router.get("/{job_id}")
async def get_job(
    job_id: str,
    user: WebUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    job: Job | None = await db.get(Job, job_id)
    if not job or job.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    return job.to_dict()


# ── Get transcript content ──────────────────────────────────────────────────

@router.get("/{job_id}/result")
async def get_result(
    job_id: str,
    user: WebUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    job: Job | None = await db.get(Job, job_id)
    if not job or job.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job.status != "done":
        raise HTTPException(status_code=425, detail="Noch nicht fertig")

    ext = {"md": "md", "txt": "txt", "json": "json"}.get(job.output_format, "md")
    result_file = RESULTS_DIR / job_id / f"transcript.{ext}"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Ergebnis nicht gefunden")

    return {
        "content": result_file.read_text(encoding="utf-8"),
        "format": job.output_format,
        "filename": job.original_filename,
    }


# ── Download transcript ─────────────────────────────────────────────────────

@router.get("/{job_id}/download")
async def download_result(
    job_id: str,
    user: WebUser,
    fmt: str = Query("md"),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    job: Job | None = await db.get(Job, job_id)
    if not job or job.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job.status != "done":
        raise HTTPException(status_code=425, detail="Noch nicht fertig")

    ext = fmt if fmt in ("md", "txt", "json") else "md"
    result_file = RESULTS_DIR / job_id / f"transcript.{ext}"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Format nicht verfügbar")

    stem = Path(job.original_filename or "transkript").stem
    return FileResponse(
        str(result_file),
        filename=f"{stem}.{ext}",
        media_type="application/octet-stream",
    )


# ── Delete job ──────────────────────────────────────────────────────────────

@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    user: WebUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    job: Job | None = await db.get(Job, job_id)
    if not job or job.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    await db.delete(job)
    await db.commit()

    # Clean up files
    shutil.rmtree(str(UPLOADS_DIR / job_id), ignore_errors=True)
    shutil.rmtree(str(RESULTS_DIR / job_id), ignore_errors=True)


# ── Current user info ───────────────────────────────────────────────────────

@router.get("/me/info", tags=["auth"])
async def me(user: WebUser) -> dict:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
    }
