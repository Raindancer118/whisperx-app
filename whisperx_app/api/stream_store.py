"""Live-stream session state for the crowd/stage protocol.

Each StreamSession tracks one inbound audio stream (e.g. from a Discord bot).
Sessions are held in memory; the raw audio is written to a per-session temp dir
so 24-hour streams never exhaust RAM.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional


StreamStatus = Literal["connecting", "streaming", "processing", "done", "failed"]


@dataclass
class StreamSession:
    session_id: str

    # Lifecycle
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    status: StreamStatus = "connecting"

    # Audio format — set during hello handshake
    audio_format: str = "pcm_s16le"   # pcm_s16le | opus | …
    sample_rate: int = 16000           # Hz
    channels: int = 1

    # On-disk accumulation
    _work_dir: Optional[Path] = field(default=None, repr=False, compare=False)
    total_bytes_received: int = 0
    processed_bytes: int = 0           # bytes already rolling-transcribed

    # Transcripts
    interim_text: str = ""                        # rough rolling result (context only)
    final_transcript: Optional[str] = None        # full WhisperX result
    corrected_transcript: Optional[str] = None    # Gemma-corrected final
    summary: Optional[str] = None                 # Gemma summary

    error: Optional[str] = None
    estimated_postprocess_seconds: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def work_dir(self) -> Path:
        if self._work_dir is None:
            self._work_dir = Path(
                tempfile.mkdtemp(prefix=f"whisperx_stream_{self.session_id[:8]}_")
            )
        return self._work_dir

    @property
    def audio_raw_path(self) -> Path:
        return self.work_dir / "audio.raw"

    def bytes_per_second(self) -> float:
        """Raw bytes per second for the declared audio format."""
        if self.audio_format == "pcm_s16le":
            return float(self.sample_rate * self.channels * 2)  # 2 bytes/sample
        # Fallback for container formats — rough estimate
        return float(self.sample_rate * self.channels * 2)

    def total_audio_seconds(self) -> float:
        bps = self.bytes_per_second()
        return self.total_bytes_received / bps if bps > 0 else 0.0

    def unprocessed_seconds(self) -> float:
        bps = self.bytes_per_second()
        return (self.total_bytes_received - self.processed_bytes) / bps if bps > 0 else 0.0

    # ------------------------------------------------------------------ #
    # Cleanup                                                              #
    # ------------------------------------------------------------------ #

    def cleanup(self) -> None:
        """Remove all temporary files for this session."""
        if self._work_dir and self._work_dir.exists():
            shutil.rmtree(self._work_dir, ignore_errors=True)


class StreamStore:
    """In-memory registry of active and recently completed stream sessions."""

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
            session = self._sessions.pop(session_id, None)
        if session:
            session.cleanup()


# Singleton shared across the FastAPI application
stream_store = StreamStore()
