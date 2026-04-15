# ============================================================
# WhisperX-App — Multi-stage Dockerfile
# Targets: api (FastAPI), worker (Celery + GPU)
# ============================================================

# ── Base: Python 3.11 with CUDA support ──────────────────────────────────
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3.11-venv python3-pip \
    ffmpeg git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

# ── API deps (lightweight — no torch/whisperx) ───────────────────────────
FROM base AS api_deps
COPY pyproject.toml README.md ./
COPY whisperx_app/__init__.py whisperx_app/
RUN pip install --upgrade pip && \
    pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" \
    "python-multipart>=0.0.9" "pydantic>=2.0" "pydantic-settings>=2.0" \
    "httpx>=0.27" "sqlalchemy[asyncio]>=2.0" "asyncpg>=0.29" \
    "celery[redis]>=5.3" "redis>=5.0" "aiosmtplib>=3.0" \
    "authlib>=1.3" "itsdangerous>=2.1" "python-jose[cryptography]>=3.3" \
    "aiofiles>=23.0" "typer[all]>=0.12" "rich>=14.0"

# ── API target ───────────────────────────────────────────────────────────
FROM api_deps AS api
COPY whisperx_app/ ./whisperx_app/
EXPOSE 8000
CMD ["uvicorn", "whisperx_app.api.main:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]

# ── Worker deps (full ML stack) ───────────────────────────────────────────
FROM base AS worker_deps
COPY pyproject.toml README.md ./
COPY whisperx_app/__init__.py whisperx_app/
RUN pip install --upgrade pip && \
    pip install "torch>=2.0" "torchaudio>=2.0" \
    "faster-whisper>=1.0" "whisperx>=3.1" "pyannote.audio>=3.1" \
    "librosa>=0.10" "soundfile>=0.12" \
    "sqlalchemy[asyncio]>=2.0" "asyncpg>=0.29" \
    "celery[redis]>=5.3" "redis>=5.0" "aiosmtplib>=3.0" \
    "pydantic>=2.0" "aiofiles>=23.0"

# ── Worker target ────────────────────────────────────────────────────────
FROM worker_deps AS worker
COPY whisperx_app/ ./whisperx_app/
CMD ["celery", "-A", "whisperx_app.celery_app", "worker", \
     "--loglevel=info", "--concurrency=1", "-Q", "transcription"]
