"""Live-stream session state for the crowd/stage protocol.

Each StreamSession tracks one inbound audio stream (e.g. from a Discord bot).
Sessions are held in memory; the raw audio is written to a shared volume
(/data/uploads/streams/<session_id>/) so the Celery worker can access it.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

# Shared between api and worker containers via the 'uploads' Docker volume.
STREAM_UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads")) / "streams"

StreamStatus = Literal["connecting", "streaming", "processing", "done", "failed"]


@dataclass
class StreamSession:
    session_id: str

    # Lifecycle
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    status: StreamStatus = "connecting"

    # Audio format — set during hello handshake
    audio_format: str = "pcm_s16le"
    sample_rate: int = 16000
    channels: int = 1

    # Byte counters
    total_bytes_received: int = 0

    # Processing metadata
    estimated_postprocess_seconds: Optional[float] = None
    error: Optional[str] = None

    # ------------------------------------------------------------------ #

    @property
    def work_dir(self) -> Path:
        """Session directory on the shared uploads volume."""
        p = STREAM_UPLOADS_DIR / self.session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def audio_raw_path(self) -> Path:
        return self.work_dir / "audio.raw"

    def bytes_per_second(self) -> float:
        if self.audio_format == "pcm_s16le":
            return float(self.sample_rate * self.channels * 2)
        return float(self.sample_rate * self.channels * 2)

    def total_audio_seconds(self) -> float:
        bps = self.bytes_per_second()
        return self.total_bytes_received / bps if bps > 0 else 0.0


class StreamStore:
    """In-memory registry of active stream sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, StreamSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self) -> StreamSession:
        session = StreamSession(session_id=str(uuid.uuid4()))
        async with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        return self._sessions.get(session_id)

    async def remove_session(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


stream_store = StreamStore()
