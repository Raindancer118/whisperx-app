"""Integration tests for the FastAPI application endpoints (async)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from whisperx_app.api.main import create_app
from whisperx_app.api.auth import _invalidate_jwks_cache
from whisperx_app.config import Config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_jwks():
    _invalidate_jwks_cache()
    yield
    _invalidate_jwks_cache()


@pytest.fixture
def rsa_pair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def _make_token(private_key, scope="transcribe", exp_offset=3600):
    from jose import jwt
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    now = int(time.time())
    return jwt.encode(
        {"sub": "u1", "scope": scope, "aud": "whisperx-app",
         "iss": "https://accounts.volantic.de", "exp": now + exp_offset},
        pem, algorithm="RS256", headers={"kid": "tid"},
    )


def _make_jwk(public_key):
    from jose import jwk
    pub_pem = public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    d = jwk.construct(pub_pem.decode(), "RS256").to_dict()
    d.update({"kid": "tid", "alg": "RS256", "use": "sig"})
    return d


@pytest.fixture
def mock_config(monkeypatch):
    cfg = Config(volantic_client_id="whisperx-app", volantic_issuer="https://accounts.volantic.de")
    monkeypatch.setattr("whisperx_app.api.auth.load_config", lambda: cfg)
    monkeypatch.setattr("whisperx_app.api.routes.transcribe.load_config", lambda: cfg)
    return cfg


@pytest.fixture
async def async_client(mock_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(base_url="http://test", transport=transport) as c:
        yield c


# ---------------------------------------------------------------------------
# Health endpoint (no auth)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_ok(async_client):
    with patch("whisperx_app.api.routes.health.list_available_models", return_value=[]):
        resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


# ---------------------------------------------------------------------------
# Auth-protected endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_requires_auth(async_client):
    content = b"fake audio"
    resp = await async_client.post(
        "/api/v1/transcribe",
        files={"audio_file": ("test.wav", content, "audio/wav")},
    )
    assert resp.status_code == 401  # HTTPBearer returns 401 when no credentials


@pytest.mark.asyncio
async def test_transcribe_rejects_expired_token(async_client, rsa_pair, mock_config):
    private, public = rsa_pair
    token = _make_token(private, exp_offset=-100)
    jwk_d = _make_jwk(public)
    with patch("whisperx_app.api.auth._get_jwks", return_value={"tid": jwk_d}):
        resp = await async_client.post(
            "/api/v1/transcribe",
            headers={"Authorization": f"Bearer {token}"},
            files={"audio_file": ("test.wav", b"audio", "audio/wav")},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_transcribe_invalid_format(async_client, rsa_pair, mock_config):
    private, public = rsa_pair
    token = _make_token(private)
    jwk_d = _make_jwk(public)
    with patch("whisperx_app.api.auth._get_jwks", return_value={"tid": jwk_d}):
        with patch("whisperx_app.api.routes.transcribe.detect_hardware",
                   return_value={"cuda": False, "device_name": None, "vram_gb": None}):
            resp = await async_client.post(
                "/api/v1/transcribe",
                headers={"Authorization": f"Bearer {token}"},
                files={"audio_file": ("test.wav", b"audio", "audio/wav")},
                data={"format": "xml"},
            )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_transcribe_enqueues_job(async_client, rsa_pair, mock_config):
    private, public = rsa_pair
    token = _make_token(private)
    jwk_d = _make_jwk(public)

    with patch("whisperx_app.api.auth._get_jwks", return_value={"tid": jwk_d}):
        with patch("whisperx_app.api.routes.transcribe.detect_hardware",
                   return_value={"cuda": False, "device_name": None, "vram_gb": None}):
            with patch("whisperx_app.api.routes.transcribe.get_audio_duration",
                       return_value=None):
                resp = await async_client.post(
                    "/api/v1/transcribe",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"audio_file": ("test.wav", b"fake audio bytes", "audio/wav")},
                )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_get_job_not_found(async_client, rsa_pair, mock_config):
    private, public = rsa_pair
    token = _make_token(private)
    jwk_d = _make_jwk(public)
    with patch("whisperx_app.api.auth._get_jwks", return_value={"tid": jwk_d}):
        resp = await async_client.get(
            "/api/v1/jobs/nonexistent-id",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_job_not_found(async_client, rsa_pair, mock_config):
    private, public = rsa_pair
    token = _make_token(private)
    jwk_d = _make_jwk(public)
    with patch("whisperx_app.api.auth._get_jwks", return_value={"tid": jwk_d}):
        resp = await async_client.delete(
            "/api/v1/jobs/nonexistent-id",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404
