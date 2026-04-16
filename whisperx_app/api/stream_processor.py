"""Stream post-processing dispatcher.

The api container has no ML dependencies (no torch / whisperx).
All heavy work (WhisperX + Gemma correction + summary) is dispatched
to the Celery worker via process_stream_task.

Results are stored in Redis so the postbox endpoint can retrieve them
even after an api-container restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whisperx_app.api.stream_store import StreamSession


# Redis key helpers
def _result_key(session_id: str) -> str:
    return f"whisperx:stream:result:{session_id}"


RESULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_CHUNK_SIZE = 2_000                  # chars per Gemma correction chunk


# =========================================================================== #
# Dispatch                                                                     #
# =========================================================================== #

def dispatch_stream_processing(session: "StreamSession") -> None:
    """Enqueue the post-processing Celery task for a completed stream."""
    from whisperx_app.tasks import process_stream_task

    process_stream_task.apply_async(
        kwargs={
            "session_id": session.session_id,
            "audio_raw_path": str(session.audio_raw_path),
            "audio_format": session.audio_format,
            "sample_rate": session.sample_rate,
            "channels": session.channels,
        },
        queue="transcription",
    )


# =========================================================================== #
# Redis result helpers (used by postbox in crowd.py)                          #
# =========================================================================== #

async def get_redis_result(session_id: str) -> dict | None:
    """Return the stored result dict from Redis, or None if not present."""
    import json
    try:
        from whisperx_app.api import session_store
        raw = await session_store.get(_result_key(session_id))
        return json.loads(raw) if raw else None
    except Exception:
        return None


# =========================================================================== #
# Time estimation (runs in api container — no ML deps needed)                 #
# =========================================================================== #

def estimate_postprocess_seconds(session: "StreamSession") -> float:
    """Rough wall-time estimate for the full post-processing pipeline."""
    audio_secs = session.total_audio_seconds()

    # WhisperX medium on CPU: roughly 0.5× real-time
    whisperx_est = audio_secs * 0.5

    # Gemma correction: ~30 s per 2 000-char chunk; ~15 chars/s of speech
    n_chunks = max(1, int(audio_secs * 15 / 2_000))
    gemma_correction_est = n_chunks * 30.0

    # Summary: ~60 s fixed
    return whisperx_est + gemma_correction_est + 60.0
