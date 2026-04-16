"""crowd / postbox endpoints — live audio ingestion and result delivery.

────────────────────────────────────────────────────────────────────────────
  CROWD PROTOCOL  (WebSocket  wss://whisperx.volantic.de/crowd?token=KEY)
────────────────────────────────────────────────────────────────────────────

  1.  crowd  →  stage   {"type": "welcome", "session_id": "<uuid>",
                          "version": "1.0"}

  2.  stage  →  crowd   {"type": "hello",  "client": "stage",
                          "format":      "pcm_s16le",
                          "sample_rate": 48000,
                          "channels":    2}

  3.  stage  →  crowd   <binary>  (audio chunk, repeat until done)

  4.  stage  →  crowd   {"type": "bye"}

  5.  crowd  →  stage   {"type": "applause",
                          "session_id":        "<uuid>",
                          "estimated_seconds": 420}

  Post-processing (WhisperX + Gemma) runs in the background Celery worker.
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

  Results are stored in Redis with a 7-day TTL and survive server restarts.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from whisperx_app.api.models import PostboxResponse
from whisperx_app.api.stream_processor import (
    dispatch_stream_processing,
    estimate_postprocess_seconds,
    get_redis_result,
)
from whisperx_app.api.stream_store import stream_store

router = APIRouter(tags=["crowd"])
log = logging.getLogger(__name__)

_CROWD_API_KEY: Optional[str] = os.environ.get("CROWD_API_KEY")
_PROTOCOL_VERSION = "1.0"


def _authorised(token: str) -> bool:
    if not _CROWD_API_KEY:
        log.warning("CROWD_API_KEY not set — accepting all connections (dev mode only!)")
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

    # ── Step 1: welcome ──────────────────────────────────────────────────── #
    await websocket.send_text(json.dumps({
        "type": "welcome",
        "session_id": session.session_id,
        "version": _PROTOCOL_VERSION,
    }))

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

                if session.status == "connecting":
                    # hello hasn't arrived yet — accept audio anyway
                    session.status = "streaming"
                continue

            # ── Text: control message ──────────────────────────────────── #
            msg_type: str = message.get("type", "")

            if msg_type == "hello":
                session.audio_format = str(message.get("format", "pcm_s16le"))
                session.sample_rate = int(message.get("sample_rate", 16000))
                session.channels = int(message.get("channels", 1))
                session.status = "streaming"
                log.info(
                    "Session %s handshake: %s %d Hz %d ch",
                    session.session_id, session.audio_format,
                    session.sample_rate, session.channels,
                )

            elif msg_type == "bye":
                graceful_bye = True
                break

            else:
                await _send_error(websocket, f"Unknown message type: {msg_type!r}")

    except WebSocketDisconnect:
        log.warning("Session %s disconnected without bye", session.session_id)

    # ── Record end time and estimate ─────────────────────────────────────── #
    session.ended_at = datetime.now(timezone.utc)
    session.estimated_postprocess_seconds = estimate_postprocess_seconds(session)

    log.info(
        "Session %s ended (graceful=%s). Audio: %.1f s. Est. postproc: %.0f s.",
        session.session_id,
        graceful_bye,
        session.total_audio_seconds(),
        session.estimated_postprocess_seconds or 0,
    )

    # ── Step 5: applause ─────────────────────────────────────────────────── #
    if graceful_bye:
        try:
            await websocket.send_text(json.dumps({
                "type": "applause",
                "session_id": session.session_id,
                "estimated_seconds": session.estimated_postprocess_seconds,
            }))
        except Exception:
            pass

    # ── Dispatch post-processing to Celery worker ─────────────────────────── #
    if session.total_bytes_received > 0:
        session.status = "processing"
        try:
            dispatch_stream_processing(session)
            log.info("Session %s dispatched to worker.", session.session_id)
        except Exception as exc:
            session.status = "failed"
            session.error = f"Failed to dispatch processing task: {exc}"
            log.error("Session %s dispatch failed: %s", session.session_id, exc)
    else:
        session.status = "failed"
        session.error = "No audio data received"
        log.warning("Session %s: no audio received.", session.session_id)


# =========================================================================== #
# HTTP  GET /api/v1/postbox/{session_id}                                      #
# =========================================================================== #

@router.get("/api/v1/postbox/{session_id}", response_model=PostboxResponse)
async def postbox(session_id: str) -> PostboxResponse:
    """Stage polls this to retrieve the session transcript and summary.

    Check order:
      1. In-memory session  (active / recently dispatched)
      2. Redis              (worker result, survives api restarts)
    """
    session = stream_store.get_session(session_id)

    if session is not None:
        if session.status in ("connecting", "streaming"):
            return PostboxResponse(status="nomailyet")

        if session.status == "processing":
            # Worker may have already finished — check Redis
            result = await get_redis_result(session_id)
            if result:
                return _postbox_from_redis(session_id, result)
            return PostboxResponse(status="nomailyet")

        if session.status == "failed":
            return PostboxResponse(
                status="wontcome",
                error=session.error or "Processing failed",
            )

        # status == "done" (shouldn't normally be set from api side)
        result = await get_redis_result(session_id)
        if result:
            return _postbox_from_redis(session_id, result)

    # Session not in memory (e.g. after api restart) — fall back to Redis
    result = await get_redis_result(session_id)
    if result:
        return _postbox_from_redis(session_id, result)

    return PostboxResponse(
        status="wontcome",
        error="Session not found — it may have expired or never existed",
    )


# =========================================================================== #
# Internal helpers                                                             #
# =========================================================================== #

def _postbox_from_redis(session_id: str, result: dict) -> PostboxResponse:
    if result.get("status") == "done":
        return PostboxResponse(
            status="maildelivery",
            session_id=session_id,
            transcript=result.get("transcript"),
            summary=result.get("summary"),
        )
    return PostboxResponse(
        status="wontcome",
        error=result.get("error", "Processing failed"),
    )


async def _send_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_text(json.dumps({"type": "error", "message": message}))
    except Exception:
        pass


async def _receive_messages(websocket: WebSocket):
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
                log.warning("Non-JSON text frame: %r", text[:100])
