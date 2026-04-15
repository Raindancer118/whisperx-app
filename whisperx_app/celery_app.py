"""Celery application factory."""

from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "whisperx_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["whisperx_app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={"whisperx_app.tasks.transcribe_job": {"queue": "transcription"}},
    worker_prefetch_multiplier=1,  # one job at a time (GPU)
    task_acks_late=True,
)
