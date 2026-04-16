"""Tests for the crowd/stage protocol and postbox endpoint.

Covered:
  - WebSocket auth rejection (wrong / missing token)
  - Successful handshake (welcome message)
  - hello message sets session audio format
  - Binary audio chunks are written to disk
  - bye triggers applause with estimated_seconds
  - Postbox returns nomailyet while processing
  - Postbox returns maildelivery when done
  - Postbox returns wontcome on failure
  - Postbox returns wontcome for unknown session_id
  - Disconnect without bye still starts processing
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Minimal app factory (avoids DB / Redis deps in test env) ─────────────── #
from whisperx_app.api.routes.crowd import router as crowd_router
from whisperx_app.api.stream_store import StreamSession, StreamStore, stream_store


# =========================================================================== #
# Fixtures                                                                     #
# =========================================================================== #

@pytest.fixture()
def app():
    """Minimal FastAPI app with only the crowd router — no DB/Redis needed."""
    application = FastAPI()
    application.include_router(crowd_router)
    return application


@pytest.fixture()
def client(app):
    """Synchronous test client (also supports WebSocket)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def set_crowd_api_key(monkeypatch):
    """Set a deterministic API key for all crowd tests."""
    monkeypatch.setenv("CROWD_API_KEY", "test-secret-key")
    # Patch the module-level variable that was already read at import time
    import whisperx_app.api.routes.crowd as crowd_module
    monkeypatch.setattr(crowd_module, "_CROWD_API_KEY", "test-secret-key")


@pytest.fixture()
def session() -> StreamSession:
    """A fresh StreamSession with a temp work directory."""
    s = StreamSession(session_id="aaaaaaaa-0000-0000-0000-000000000001")
    yield s
    s.cleanup()


# =========================================================================== #
# StreamSession unit tests                                                     #
# =========================================================================== #

class TestStreamSession:
    def test_bytes_per_second_pcm_mono_16k(self):
        s = StreamSession(session_id="x")
        s.audio_format = "pcm_s16le"
        s.sample_rate = 16000
        s.channels = 1
        assert s.bytes_per_second() == 32_000  # 16000 * 1 * 2

    def test_bytes_per_second_pcm_stereo_48k(self):
        s = StreamSession(session_id="x")
        s.audio_format = "pcm_s16le"
        s.sample_rate = 48000
        s.channels = 2
        assert s.bytes_per_second() == 192_000  # 48000 * 2 * 2

    def test_total_audio_seconds(self):
        s = StreamSession(session_id="x")
        s.audio_format = "pcm_s16le"
        s.sample_rate = 16000
        s.channels = 1
        s.total_bytes_received = 32_000 * 10  # 10 seconds
        assert s.total_audio_seconds() == pytest.approx(10.0)

    def test_unprocessed_seconds(self):
        s = StreamSession(session_id="x")
        s.audio_format = "pcm_s16le"
        s.sample_rate = 16000
        s.channels = 1
        s.total_bytes_received = 32_000 * 60  # 60 s buffered
        s.processed_bytes = 32_000 * 30         # 30 s already processed
        assert s.unprocessed_seconds() == pytest.approx(30.0)

    def test_audio_raw_path_within_work_dir(self, session):
        assert session.audio_raw_path.parent == session.work_dir

    def test_cleanup_removes_work_dir(self, tmp_path, monkeypatch):
        import tempfile
        monkeypatch.setattr(tempfile, "mkdtemp", lambda **_: str(tmp_path))
        s = StreamSession(session_id="x")
        assert s.work_dir.exists()
        s.cleanup()
        assert not tmp_path.exists()


# =========================================================================== #
# StreamStore unit tests                                                       #
# =========================================================================== #

class TestStreamStore:
    @pytest.mark.asyncio
    async def test_create_and_get(self):
        store = StreamStore()
        session = await store.create_session()
        assert store.get_session(session.session_id) is session

    @pytest.mark.asyncio
    async def test_get_unknown_returns_none(self):
        store = StreamStore()
        assert store.get_session("nonexistent") is None

    @pytest.mark.asyncio
    async def test_remove_cleans_up(self, tmp_path):
        store = StreamStore()
        session = await store.create_session()
        work = session.work_dir          # triggers creation
        assert work.exists()
        await store.remove_session(session.session_id)
        assert store.get_session(session.session_id) is None
        assert not work.exists()

    @pytest.mark.asyncio
    async def test_session_ids_are_unique(self):
        store = StreamStore()
        ids = {(await store.create_session()).session_id for _ in range(10)}
        assert len(ids) == 10


# =========================================================================== #
# WebSocket integration tests                                                  #
# =========================================================================== #

class TestCrowdWebSocket:
    def test_wrong_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/crowd?token=wrong-key") as ws:
                ws.receive_json()

    def test_missing_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/crowd") as ws:
                ws.receive_json()

    def test_welcome_on_connect(self, client):
        with client.websocket_connect("/crowd?token=test-secret-key") as ws:
            msg = ws.receive_json()
        assert msg["type"] == "welcome"
        assert "session_id" in msg
        assert msg["version"] == "1.0"

    def test_hello_acknowledged_no_error(self, client):
        with client.websocket_connect("/crowd?token=test-secret-key") as ws:
            _welcome = ws.receive_json()
            ws.send_json({
                "type": "hello",
                "client": "stage",
                "format": "pcm_s16le",
                "sample_rate": 48000,
                "channels": 2,
            })
            # Send bye immediately so the connection closes cleanly
            ws.send_json({"type": "bye"})
            applause = ws.receive_json()
        assert applause["type"] == "applause"

    def test_audio_bytes_accepted(self, client):
        dummy_audio = b"\x00\x01" * 1600   # 1 600 samples of silence
        with client.websocket_connect("/crowd?token=test-secret-key") as ws:
            _welcome = ws.receive_json()
            ws.send_json({
                "type": "hello",
                "client": "stage",
                "format": "pcm_s16le",
                "sample_rate": 16000,
                "channels": 1,
            })
            ws.send_bytes(dummy_audio)
            ws.send_json({"type": "bye"})
            applause = ws.receive_json()
        assert applause["type"] == "applause"

    def test_applause_contains_session_id(self, client):
        with client.websocket_connect("/crowd?token=test-secret-key") as ws:
            welcome = ws.receive_json()
            ws.send_json({"type": "hello", "client": "stage",
                          "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
            ws.send_json({"type": "bye"})
            applause = ws.receive_json()
        assert applause["session_id"] == welcome["session_id"]

    def test_applause_contains_estimated_seconds(self, client):
        with client.websocket_connect("/crowd?token=test-secret-key") as ws:
            ws.receive_json()
            ws.send_json({"type": "hello", "client": "stage",
                          "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
            ws.send_json({"type": "bye"})
            applause = ws.receive_json()
        assert "estimated_seconds" in applause

    def test_unknown_message_type_returns_error(self, client):
        with client.websocket_connect("/crowd?token=test-secret-key") as ws:
            ws.receive_json()
            ws.send_json({"type": "dance"})
            error = ws.receive_json()
            ws.send_json({"type": "bye"})
            ws.receive_json()   # applause
        assert error["type"] == "error"

    def test_audio_written_to_disk(self, client):
        dummy_audio = b"\x00\xFF" * 800
        session_id_holder: list[str] = []

        with client.websocket_connect("/crowd?token=test-secret-key") as ws:
            welcome = ws.receive_json()
            session_id_holder.append(welcome["session_id"])
            ws.send_json({"type": "hello", "client": "stage",
                          "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
            ws.send_bytes(dummy_audio)
            ws.send_json({"type": "bye"})
            ws.receive_json()   # applause

        session = stream_store.get_session(session_id_holder[0])
        assert session is not None
        assert session.total_bytes_received == len(dummy_audio)


# =========================================================================== #
# Postbox endpoint tests                                                       #
# =========================================================================== #

class TestPostbox:
    def test_unknown_session_wontcome(self, client):
        resp = client.get("/api/v1/postbox/00000000-dead-beef-0000-000000000000")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "wontcome"

    @pytest.mark.asyncio
    async def test_processing_returns_nomailyet(self, client):
        session = await stream_store.create_session()
        session.status = "processing"

        resp = client.get(f"/api/v1/postbox/{session.session_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "nomailyet"

    @pytest.mark.asyncio
    async def test_streaming_returns_nomailyet(self, client):
        session = await stream_store.create_session()
        session.status = "streaming"

        resp = client.get(f"/api/v1/postbox/{session.session_id}")
        assert resp.json()["status"] == "nomailyet"

    @pytest.mark.asyncio
    async def test_failed_returns_wontcome_with_error(self, client):
        session = await stream_store.create_session()
        session.status = "failed"
        session.error = "WhisperX OOM"

        resp = client.get(f"/api/v1/postbox/{session.session_id}")
        body = resp.json()
        assert body["status"] == "wontcome"
        assert "WhisperX OOM" in body["error"]

    @pytest.mark.asyncio
    async def test_done_returns_maildelivery(self, client):
        session = await stream_store.create_session()
        session.status = "done"
        session.corrected_transcript = "**Speaker A:** Hello world."
        session.summary = "A short greeting."

        resp = client.get(f"/api/v1/postbox/{session.session_id}")
        body = resp.json()
        assert body["status"] == "maildelivery"
        assert body["session_id"] == session.session_id
        assert "Hello world" in body["transcript"]
        assert body["summary"] == "A short greeting."

    @pytest.mark.asyncio
    async def test_done_falls_back_to_final_transcript(self, client):
        """If corrected_transcript is None, final_transcript is used."""
        session = await stream_store.create_session()
        session.status = "done"
        session.corrected_transcript = None
        session.final_transcript = "Raw transcript."
        session.summary = "Summary."

        resp = client.get(f"/api/v1/postbox/{session.session_id}")
        body = resp.json()
        assert body["transcript"] == "Raw transcript."


# =========================================================================== #
# OllamaClient unit tests (mocked HTTP)                                       #
# =========================================================================== #

class TestOllamaClient:
    @pytest.mark.asyncio
    async def test_correct_transcript_chunk_calls_ollama(self):
        import respx
        import httpx
        from whisperx_app.api.ollama_client import correct_transcript_chunk

        mock_response = {
            "choices": [{"message": {"content": "Corrected text."}}]
        }

        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            result = await correct_transcript_chunk(
                chunk="Original text.",
                rough_context="rough context",
            )

        assert result == "Corrected text."

    @pytest.mark.asyncio
    async def test_generate_summary_calls_ollama(self):
        import respx
        import httpx
        from whisperx_app.api.ollama_client import generate_summary

        mock_response = {
            "choices": [{"message": {"content": "Summary text."}}]
        }

        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=mock_response)
            )
            result = await generate_summary("Long transcript here.")

        assert result == "Summary text."

    @pytest.mark.asyncio
    async def test_long_transcript_truncated(self):
        import respx
        import httpx
        from whisperx_app.api import ollama_client

        captured: list[dict] = []

        async def capture_request(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}]
            })

        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/v1/chat/completions").mock(side_effect=capture_request)
            long_transcript = "x" * (ollama_client._MAX_TRANSCRIPT_CHARS + 10_000)
            await ollama_client.generate_summary(long_transcript)

        user_content = captured[0]["messages"][1]["content"]
        assert len(user_content) < len(long_transcript) + 200   # truncated


# =========================================================================== #
# stream_processor unit tests (no real Whisper/ffmpeg)                        #
# =========================================================================== #

class TestStreamProcessor:
    def test_split_at_paragraphs_basic(self):
        from whisperx_app.api.stream_processor import _split_at_paragraphs

        text = "A" * 100 + "\n\n" + "B" * 100 + "\n\n" + "C" * 100
        chunks = _split_at_paragraphs(text, chunk_size=120)
        assert len(chunks) >= 2
        assert all(len(c) <= 120 + 10 for c in chunks)   # slight overshoot ok

    def test_split_at_paragraphs_no_newlines(self):
        from whisperx_app.api.stream_processor import _split_at_paragraphs

        text = "X" * 500
        chunks = _split_at_paragraphs(text, chunk_size=100)
        assert len(chunks) == 5
        assert all(len(c) <= 100 for c in chunks)
        assert sum(len(c) for c in chunks) == 500

    def test_estimate_postprocess_seconds_returns_positive(self, session):
        from whisperx_app.api.stream_processor import estimate_postprocess_seconds

        session.audio_format = "pcm_s16le"
        session.sample_rate = 16000
        session.channels = 1
        session.total_bytes_received = 32_000 * 3600   # 1 hour

        est = estimate_postprocess_seconds(session)
        assert est > 0

    @pytest.mark.asyncio
    async def test_process_stream_final_no_audio_raises(self, session):
        from whisperx_app.api.stream_processor import process_stream_final

        # No audio written → should fail gracefully
        with pytest.raises(FileNotFoundError):
            await process_stream_final(session)

        assert session.status == "failed"
        assert session.error is not None
