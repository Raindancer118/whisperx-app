"""In-memory job store and background worker for transcription jobs.

MVP implementation using an asyncio.Queue and a single background worker task.
For multi-worker deployments, replace this with Redis + Celery.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


class Job:
    def __init__(self, job_id: str, fmt: str):
        self.job_id = job_id
        self.status: str = "queued"
        self.created_at: datetime = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None
        self.format: str = fmt
        self.result: Optional[str] = None
        self.segments: Optional[list[dict[str, Any]]] = None
        self.error: Optional[str] = None
        self.progress_pct: Optional[int] = None
        self._audio_bytes: Optional[bytes] = None
        self._params: dict[str, Any] = {}


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def start_worker(self) -> None:
        self._worker_task = asyncio.create_task(self._worker())

    async def stop_worker(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def create_job(self, fmt: str, params: dict, audio_bytes: bytes) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, fmt=fmt)
        job._params = params
        job._audio_bytes = audio_bytes
        self._jobs[job_id] = job
        self._queue.put_nowait(job_id)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def delete_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            job = self._jobs[job_id]
            if job.status in ("queued", "processing"):
                job.status = "cancelled"
            del self._jobs[job_id]
            return True
        return False

    async def _worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self._jobs.get(job_id)
            if not job or job.status == "cancelled":
                self._queue.task_done()
                continue

            job.status = "processing"
            job.progress_pct = 0

            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._run_transcription, job
                )
                job.status = "done"
                job.completed_at = datetime.now(timezone.utc)
                job.progress_pct = 100
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.completed_at = datetime.now(timezone.utc)
            finally:
                self._queue.task_done()

    def _run_transcription(self, job: Job) -> None:
        """Blocking transcription call — runs in a thread executor."""
        import tempfile
        from pathlib import Path

        from whisperx_app.config import load_config
        from whisperx_app.formatter import format_result
        from whisperx_app.transcriber import transcribe

        cfg = load_config()
        params = job._params

        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
            f.write(job._audio_bytes)
            tmp_path = Path(f.name)

        try:
            result = transcribe(
                audio_path=tmp_path,
                model_name=params.get("model", cfg.default_model),
                device=params.get("device", "cpu"),
                compute_type=params.get("compute_type", "int8"),
                hf_token=params.get("hf_token"),
                diarize=params.get("diarize", True),
                language=params.get("language"),
                batch_size=params.get("batch_size", cfg.api_batch_size_cpu),
            )
            job.segments = result.get("segments", [])
            job.result = format_result(
                result=result,
                fmt=job.format,
                model_name=params.get("model", cfg.default_model),
                speaker_names=params.get("speaker_names"),
            )
        finally:
            tmp_path.unlink(missing_ok=True)


# Singleton — shared across the FastAPI application
job_store = JobStore()
