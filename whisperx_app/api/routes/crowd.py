"""crowd / postbox endpoints — live audio ingestion and result delivery.

────────────────────────────────────────────────────────────────────────────
  CROWD PROTOCOL  (WebSocket  wss://host/crowd?token=<CROWD_API_KEY>)
────────────────────────────────────────────────────────────────────────────

  1.  crowd  →  stage   {"type": "welcome", "session_id": "<uuid>",
                          "version": "1.0"}

  2.  stage  →  crowd   {"type": "hello",  "client": "stage",
                          "format":      "pcm_s16le",   ← or "opus"
                          "sample_rate": 48000,
                          "channels":    2}

  3.  stage  →  crowd   <binary>  (audio chunk, repeat until done)

  4.  stage  →  crowd   {"type": "bye"}

  5.  crowd  →  stage   {"type": "applause",
                          "session_id":        "<uuid>",
                          "estimated_seconds": 420}

  After applause, post-processing starts in the background.
  Stage polls /api/v1/postbox/{session_id} for the result.

────────────────────────────────────────────────────────────────────────────
  POSTBOX  (HTTP  GET /api/v1/postbox/{session_id})
────────────────────────────────────────────────────────────────────────────

  While processing:   {"status": "nomailyet"}
  On failure:         {"status": "wontcome", "error": "<message>"}
  On success:         {"status": "maildelivery",
                        "session_id":  "<uuid>",
                        "transcript":  "<corrected markdown>",
                        "summary":     "<structured summary>"}

────────────────────────────────────────────────────────────────────────────
  AUDIO FORMAT NOTES
────────────────────────────────────────────────────────────────────────────

  Recommended: pcm_s16le at 16 000 Hz, 1 channel  (lowest bandwidth)
  Discord default: pcm_s16le at 48 000 Hz, 2 channels
  Other container formats (opus, webm …) accepted — ffmpeg converts them.

────────────────────────────────────────────────────────────────────────────
  SECURITY
────────────────────────────────────────────────────────────────────────────

  Set CROWD_API_KEY to a long random secret.
  TLS termination is handled by nginx (see nginx/nginx.conf).
  Without CROWD_API_KEY the server logs a warning and accepts all connections
  (useful for local development only — never leave unset in production).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from whisperx_app.api.models import PostboxResponse
from whisperx_app.api.stream_processor import (
    estimate_postprocess_seconds,
    process_stream_final,
    rolling_transcription_loop,
)
from whisperx_app.api.stream_store import stream_store

router = APIRouter(tags=["crowd"])
log = logging.getLogger(__name__)

_CROWD_API_KEY: Optional[str] = os.environ.get("CROWD_API_KEY")
_PROTOCOL_VERSION = "1.0"


# =========================================================================== #
# Auth helper                                                                  #
# =========================================================================== #

def _authorised(token: str) -> bool:
    if not _CROWD_API_KEY:
        log.warning(
            "CROWD_API_KEY is not set — accepting all connections (dev mode only!)"
        )
        return True
    return token == _CROWD_API_KEY


# =========================================================================== #
# WebSocket  /crowd                                                            #
# =========================================================================== #

@router.websocket("/crowd")
async def crowd_websocket(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    """Live audio ingestion endpoint for Discord stage bots."""

    if not _authorised(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    session = await stream_store.create_session()
    log.info("New crowd session: %s", session.session_id)

    # ── Step 1: send welcome ─────────────────────────────────────────────── #
    await websocket.send_text(json.dumps({
        "type": "welcome",
        "session_id": session.session_id,
        "version": _PROTOCOL_VERSION,
    }))

    rolling_task: Optional[asyncio.Task] = None
    graceful_bye = False

    try:
        async for message in _receive_messages(websocket):
            kind = message.get("kind")

            # ── Binary: audio chunk ────────────────────────────────────── #
            if kind == "bytes":
                chunk: bytes = message["data"]
                with open(session.audio_raw_path, "ab") as fh:
                    fh.write(chunk)
                session.total_bytes_received += len(chunk)

                # Start rolling transcription on first audio after handshake
                if session.status == "streaming" and rolling_task is None:
                    rolling_task = asyncio.create_task(
                        rolling_transcription_loop(session),
                        name=f"rolling_{session.session_id[:8]}",
                    )
                continue

            # ── Text: control message ──────────────────────────────────── #
            msg_type: str = message.get("type", "")

            if msg_type == "hello":
                session.audio_format = str(message.get("format", "pcm_s16le"))
                session.sample_rate = int(message.get("sample_rate", 16000))
                session.channels = int(message.get("channels", 1))
                session.status = "streaming"
                log.info(
                    "Session %s handshake: %s  %d Hz  %d ch",
                    session.session_id,
                    session.audio_format,
                    session.sample_rate,
                    session.channels,
                )

            elif msg_type == "bye":
                graceful_bye = True
                break

            else:
                await _send_error(websocket, f"Unknown message type: {msg_type!r}")

    except WebSocketDisconnect:
        log.warning(
            "Session %s: WebSocket disconnected without bye", session.session_id
        )
    finally:
        if rolling_task and not rolling_task.done():
            rolling_task.cancel()
            try:
                await rolling_task
            except asyncio.CancelledError:
                pass

    session.ended_at = datetime.now(timezone.utc)
    session.estimated_postprocess_seconds = estimate_postprocess_seconds(session)

    log.info(
        "Session %s ended (graceful=%s). Audio: %.1f s.  Est. postproc: %.0f s.",
        session.session_id,
        graceful_bye,
        session.total_audio_seconds(),
        session.estimated_postprocess_seconds or 0,
    )

    # ── Step 5: send applause ────────────────────────────────────────────── #
    if graceful_bye:
        try:
            await websocket.send_text(json.dumps({
                "type": "applause",
                "session_id": session.session_id,
                "estimated_seconds": session.estimated_postprocess_seconds,
            }))
        except Exception:
            pass  # WebSocket may have closed already

    # ── Background: full post-processing pipeline ────────────────────────── #
    if session.total_bytes_received > 0:
        asyncio.create_task(
            _run_final_processing(session),
            name=f"finalproc_{session.session_id[:8]}",
        )
    else:
        session.status = "failed"
        session.error = "No audio data received"


# =========================================================================== #
# HTTP  GET /api/v1/postbox/{session_id}                                      #
# =========================================================================== #

@router.get("/api/v1/postbox/{session_id}", response_model=PostboxResponse)
async def postbox(session_id: str) -> PostboxResponse:
    """Stage polls this endpoint to check whether the session result is ready."""
    session = stream_store.get_session(session_id)

    if session is None:
        return PostboxResponse(
            status="wontcome",
            error="Session not found — either it never existed or has been cleaned up",
        )

    if session.status in ("connecting", "streaming", "processing"):
        return PostboxResponse(status="nomailyet")

    if session.status == "failed":
        return PostboxResponse(
            status="wontcome",
            error=session.error or "Post-processing failed for an unknown reason",
        )

    # status == "done"
    return PostboxResponse(
        status="maildelivery",
        session_id=session_id,
        transcript=session.corrected_transcript or session.final_transcript,
        summary=session.summary,
    )


# =========================================================================== #
# Internal helpers                                                             #
# =========================================================================== #

async def _run_final_processing(session) -> None:
    """Wrapper so errors don't silently vanish from the background task."""
    try:
        await process_stream_final(session)
    except Exception as exc:
        log.error(
            "Session %s: final processing raised: %s", session.session_id, exc,
            exc_info=True,
        )


async def _send_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_text(json.dumps({"type": "error", "message": message}))
    except Exception:
        pass


async def _receive_messages(websocket: WebSocket):
    """Yield normalised dicts from a WebSocket until disconnect."""
    while True:
        try:
            raw = await websocket.receive()
        except WebSocketDisconnect:
            return

        if raw["type"] == "websocket.disconnect":
            return

        if raw.get("bytes") is not None:
            yield {"kind": "bytes", "data": raw["bytes"]}
            continue

        text = raw.get("text")
        if text:
            try:
                parsed = json.loads(text)
                parsed.setdefault("kind", "text")
                yield parsed
            except json.JSONDecodeError:
                log.warning("Received non-JSON text frame: %r", text[:100])
