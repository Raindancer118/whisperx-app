"""Tests for the crowd/stage protocol and postbox endpoint.

Covered:
  - StreamSession unit tests
  - StreamStore unit tests
  - WebSocket handshake / auth / audio / bye-applause
  - Postbox responses (nomailyet, maildelivery, wontcome)
  - OllamaClient (mocked HTTP)
  - estimate_postprocess_seconds
  - _split_at_paragraphs (in tasks.py)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from whisperx_app.api.routes.crowd import router as crowd_router
from whisperx_app.api.stream_store import StreamSession, StreamStore, stream_store


# =========================================================================== #
# Fixtures                                                                     #
# =========================================================================== #

@pytest.fixture()
def app():
    """Minimal FastAPI app with only the crowd router."""
    application = FastAPI()
    application.include_router(crowd_router)
    return application


@pytest.fixture()
def client(app, tmp_path, monkeypatch):
    """Test client with UPLOADS_DIR pointed at a tmp dir."""
    import whisperx_app.api.stream_store as ss_mod
    monkeypatch.setattr(ss_mod, "STREAM_UPLOADS_DIR", tmp_path / "streams")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def set_crowd_api_key(monkeypatch):
    monkeypatch.setenv("CROWD_API_KEY", "test-secret-key")
    import whisperx_app.api.routes.crowd as crowd_mod
    monkeypatch.setattr(crowd_mod, "_CROWD_API_KEY", "test-secret-key")


@pytest.fixture()
def tmp_session(tmp_path, monkeypatch) -> StreamSession:
    import whisperx_app.api.stream_store as ss_mod
    monkeypatch.setattr(ss_mod, "STREAM_UPLOADS_DIR", tmp_path / "streams")
    s = StreamSession(session_id="aaaaaaaa-0000-0000-0000-000000000001")
    yield s


# =========================================================================== #
# StreamSession unit tests                                                     #
# =========================================================================== #

class TestStreamSession:
    def test_bytes_per_second_pcm_mono_16k(self):
        s = StreamSession(session_id="x")
        s.audio_format = "pcm_s16le"
        s.sample_rate = 16000
        s.channels = 1
        assert s.bytes_per_second() == 32_000

    def test_bytes_per_second_pcm_stereo_48k(self):
        s = StreamSession(session_id="x")
        s.audio_format = "pcm_s16le"
        s.sample_rate = 48000
        s.channels = 2
        assert s.bytes_per_second() == 192_000

    def test_total_audio_seconds(self):
        s = StreamSession(session_id="x")
        s.audio_format = "pcm_s16le"
        s.sample_rate = 16000
        s.channels = 1
        s.total_bytes_received = 32_000 * 10
        assert s.total_audio_seconds() == pytest.approx(10.0)

    def test_audio_raw_path_within_work_dir(self, tmp_session):
        assert tmp_session.audio_raw_path.parent == tmp_session.work_dir

    def test_work_dir_created_on_access(self, tmp_session):
        assert tmp_session.work_dir.exists()


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
    async def test_remove_session(self):
        store = StreamStore()
        session = await store.create_session()
        await store.remove_session(session.session_id)
        assert store.get_session(session.session_id) is None

    @pytest.mark.asyncio
    async def test_session_ids_are_unique(self):
        store = StreamStore()
        ids = {(await store.create_session()).session_id for _ in range(10)}
        assert len(ids) == 10


# =========================================================================== #
# WebSocket integration tests                                                  #
# =========================================================================== #

class TestCrowdWebSocket:

    def _mock_dispatch(self):
        """Patch dispatch_stream_processing so no real Celery call is made."""
        return patch("whisperx_app.api.routes.crowd.dispatch_stream_processing")

    def test_wrong_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/crowd?token=wrong-key") as ws:
                ws.receive_json()

    def test_missing_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/crowd") as ws:
                ws.receive_json()

    def test_welcome_on_connect(self, client):
        with self._mock_dispatch():
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                msg = ws.receive_json()
        assert msg["type"] == "welcome"
        assert "session_id" in msg
        assert msg["version"] == "1.0"

    def test_hello_then_bye_returns_applause(self, client):
        with self._mock_dispatch():
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                ws.receive_json()   # welcome
                ws.send_json({"type": "hello", "client": "stage",
                              "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ws.send_json({"type": "bye"})
                applause = ws.receive_json()
        assert applause["type"] == "applause"

    def test_applause_contains_session_id(self, client):
        with self._mock_dispatch():
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                welcome = ws.receive_json()
                ws.send_json({"type": "hello", "client": "stage",
                              "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ws.send_json({"type": "bye"})
                applause = ws.receive_json()
        assert applause["session_id"] == welcome["session_id"]

    def test_applause_contains_estimated_seconds(self, client):
        with self._mock_dispatch():
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                ws.receive_json()
                ws.send_json({"type": "hello", "client": "stage",
                              "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ws.send_json({"type": "bye"})
                applause = ws.receive_json()
        assert "estimated_seconds" in applause

    def test_audio_bytes_accepted(self, client):
        dummy = b"\x00\x01" * 1600
        with self._mock_dispatch():
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                ws.receive_json()
                ws.send_json({"type": "hello", "client": "stage",
                              "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ws.send_bytes(dummy)
                ws.send_json({"type": "bye"})
                applause = ws.receive_json()
        assert applause["type"] == "applause"

    def test_unknown_message_returns_error(self, client):
        with self._mock_dispatch():
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                ws.receive_json()
                ws.send_json({"type": "dance"})
                error = ws.receive_json()
                ws.send_json({"type": "bye"})
                ws.receive_json()   # applause
        assert error["type"] == "error"

    def test_audio_bytes_written_to_disk(self, client):
        dummy = b"\x00\xFF" * 800
        session_ids: list[str] = []

        with self._mock_dispatch():
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                welcome = ws.receive_json()
                session_ids.append(welcome["session_id"])
                ws.send_json({"type": "hello", "client": "stage",
                              "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ws.send_bytes(dummy)
                ws.send_json({"type": "bye"})
                ws.receive_json()

        session = stream_store.get_session(session_ids[0])
        assert session is not None
        assert session.total_bytes_received == len(dummy)

    def test_dispatch_called_when_audio_received(self, client):
        dummy = b"\x00\x01" * 100
        with patch("whisperx_app.api.routes.crowd.dispatch_stream_processing") as mock_dispatch:
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                ws.receive_json()
                ws.send_json({"type": "hello", "client": "stage",
                              "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ws.send_bytes(dummy)
                ws.send_json({"type": "bye"})
                ws.receive_json()
        mock_dispatch.assert_called_once()

    def test_no_dispatch_when_no_audio(self, client):
        with patch("whisperx_app.api.routes.crowd.dispatch_stream_processing") as mock_dispatch:
            with client.websocket_connect("/crowd?token=test-secret-key") as ws:
                ws.receive_json()
                ws.send_json({"type": "hello", "client": "stage",
                              "format": "pcm_s16le", "sample_rate": 16000, "channels": 1})
                ws.send_json({"type": "bye"})
                ws.receive_json()
        mock_dispatch.assert_not_called()


# =========================================================================== #
# Postbox endpoint tests                                                       #
# =========================================================================== #

class TestPostbox:

    def _no_redis(self):
        """Patch get_redis_result to always return None (no Redis in unit tests)."""
        return patch("whisperx_app.api.routes.crowd.get_redis_result",
                     return_value=None)

    def test_unknown_session_wontcome(self, client):
        with self._no_redis():
            resp = client.get("/api/v1/postbox/00000000-dead-beef-0000-000000000000")
        assert resp.status_code == 200
        assert resp.json()["status"] == "wontcome"

    @pytest.mark.asyncio
    async def test_processing_returns_nomailyet(self, client):
        with self._no_redis():
            session = await stream_store.create_session()
            session.status = "processing"
            resp = client.get(f"/api/v1/postbox/{session.session_id}")
        assert resp.json()["status"] == "nomailyet"

    @pytest.mark.asyncio
    async def test_streaming_returns_nomailyet(self, client):
        with self._no_redis():
            session = await stream_store.create_session()
            session.status = "streaming"
            resp = client.get(f"/api/v1/postbox/{session.session_id}")
        assert resp.json()["status"] == "nomailyet"

    @pytest.mark.asyncio
    async def test_failed_returns_wontcome(self, client):
        with self._no_redis():
            session = await stream_store.create_session()
            session.status = "failed"
            session.error = "WhisperX OOM"
            resp = client.get(f"/api/v1/postbox/{session.session_id}")
        body = resp.json()
        assert body["status"] == "wontcome"
        assert "WhisperX OOM" in body["error"]

    @pytest.mark.asyncio
    async def test_processing_with_redis_result_returns_maildelivery(self, client):
        redis_result = {
            "status": "done",
            "transcript": "**Speaker A:** Hello.",
            "summary": "A greeting.",
        }
        with patch("whisperx_app.api.routes.crowd.get_redis_result",
                   return_value=redis_result):
            session = await stream_store.create_session()
            session.status = "processing"
            resp = client.get(f"/api/v1/postbox/{session.session_id}")
        body = resp.json()
        assert body["status"] == "maildelivery"
        assert "Hello" in body["transcript"]

    def test_redis_result_returned_when_session_not_in_memory(self, client):
        redis_result = {
            "status": "done",
            "transcript": "Remote transcript.",
            "summary": "Remote summary.",
        }
        with patch("whisperx_app.api.routes.crowd.get_redis_result",
                   return_value=redis_result):
            resp = client.get("/api/v1/postbox/some-session-that-is-not-in-memory")
        body = resp.json()
        assert body["status"] == "maildelivery"
        assert body["transcript"] == "Remote transcript."

    def test_redis_failure_returned_as_wontcome(self, client):
        redis_result = {"status": "failed", "error": "Worker crashed"}
        with patch("whisperx_app.api.routes.crowd.get_redis_result",
                   return_value=redis_result):
            resp = client.get("/api/v1/postbox/some-failed-session")
        body = resp.json()
        assert body["status"] == "wontcome"
        assert "Worker crashed" in body["error"]


# =========================================================================== #
# OllamaClient unit tests (mocked HTTP)                                       #
# =========================================================================== #

class TestOllamaClient:

    @pytest.mark.asyncio
    async def test_correct_transcript_chunk(self):
        import respx, httpx
        from whisperx_app.api.ollama_client import correct_transcript_chunk

        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={
                    "choices": [{"message": {"content": "Corrected."}}]
                })
            )
            result = await correct_transcript_chunk(chunk="Original.")
        assert result == "Corrected."

    @pytest.mark.asyncio
    async def test_generate_summary(self):
        import respx, httpx
        from whisperx_app.api.ollama_client import generate_summary

        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={
                    "choices": [{"message": {"content": "Summary."}}]
                })
            )
            result = await generate_summary("Long transcript.")
        assert result == "Summary."

    @pytest.mark.asyncio
    async def test_long_transcript_truncated(self):
        import respx, httpx
        from whisperx_app.api import ollama_client

        captured: list[dict] = []

        async def capture(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}]
            })

        with respx.mock(base_url="http://localhost:11434") as mock:
            mock.post("/v1/chat/completions").mock(side_effect=capture)
            long = "x" * (ollama_client._MAX_TRANSCRIPT_CHARS + 10_000)
            await ollama_client.generate_summary(long)

        user_content = captured[0]["messages"][1]["content"]
        assert len(user_content) < len(long) + 200


# =========================================================================== #
# stream_processor unit tests                                                  #
# =========================================================================== #

class TestStreamProcessor:

    def test_estimate_postprocess_seconds_returns_positive(self, tmp_session):
        from whisperx_app.api.stream_processor import estimate_postprocess_seconds

        tmp_session.audio_format = "pcm_s16le"
        tmp_session.sample_rate = 16000
        tmp_session.channels = 1
        tmp_session.total_bytes_received = 32_000 * 3600   # 1 hour
        assert estimate_postprocess_seconds(tmp_session) > 0


# =========================================================================== #
# tasks._split_at_paragraphs unit tests                                       #
# =========================================================================== #

class TestSplitAtParagraphs:

    def test_basic_paragraph_split(self):
        from whisperx_app.api.text_utils import split_at_paragraphs as _split_at_paragraphs

        text = "A" * 100 + "\n\n" + "B" * 100 + "\n\n" + "C" * 100
        chunks = _split_at_paragraphs(text, chunk_size=120)
        assert len(chunks) >= 2
        assert all(len(c) <= 120 + 10 for c in chunks)

    def test_no_newlines_hard_cut(self):
        from whisperx_app.api.text_utils import split_at_paragraphs as _split_at_paragraphs

        text = "X" * 500
        chunks = _split_at_paragraphs(text, chunk_size=100)
        assert len(chunks) == 5
        assert all(len(c) <= 100 for c in chunks)
        assert sum(len(c) for c in chunks) == 500

    def test_short_text_not_split(self):
        from whisperx_app.api.text_utils import split_at_paragraphs as _split_at_paragraphs

        text = "Short text."
        chunks = _split_at_paragraphs(text, chunk_size=1000)
        assert chunks == ["Short text."]
