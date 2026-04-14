"""Tests for api/auth.py — JWT validation with a synthetic RS256 key pair."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from whisperx_app.api.auth import AuthError, _invalidate_jwks_cache, validate_token
from whisperx_app.config import Config


# ---------------------------------------------------------------------------
# Key generation helpers
# ---------------------------------------------------------------------------

def _generate_rsa_key_pair():
    """Generate a fresh RSA key pair for test signing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key, private_key.public_key()


def _make_test_token(
    private_key,
    kid: str = "test-kid",
    sub: str = "user123",
    scope: str = "transcribe",
    aud: str = "whisperx-app",
    iss: str = "https://accounts.volantic.de",
    exp_offset: int = 3600,
) -> str:
    """Create a signed RS256 JWT with given claims."""
    from jose import jwt as jose_jwt

    now = int(time.time())
    payload = {
        "sub": sub,
        "scope": scope,
        "aud": aud,
        "iss": iss,
        "exp": now + exp_offset,
        "iat": now,
        "jti": "test-jti",
    }
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jose_jwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})


def _public_key_to_jwk(public_key, kid: str = "test-kid") -> dict:
    """Convert an RSA public key to a JWK dict for mocking."""
    from jose.backends import RSAKey
    from jose import jwk

    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    rsa_key = jwk.construct(pub_pem.decode(), algorithm="RS256")
    key_dict = rsa_key.to_dict()
    key_dict["kid"] = kid
    key_dict["alg"] = "RS256"
    key_dict["use"] = "sig"
    return key_dict


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def rsa_pair():
    return _generate_rsa_key_pair()


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    _invalidate_jwks_cache()
    yield
    _invalidate_jwks_cache()


@pytest.fixture
def mock_config(monkeypatch):
    cfg = Config(
        volantic_client_id="whisperx-app",
        volantic_issuer="https://accounts.volantic.de",
    )
    monkeypatch.setattr("whisperx_app.api.auth.load_config", lambda: cfg)
    return cfg


async def _mock_get_jwks(jwk_dict: dict):
    return {jwk_dict["kid"]: jwk_dict}


@pytest.mark.asyncio
async def test_valid_token(rsa_pair, mock_config):
    private_key, public_key = rsa_pair
    token = _make_test_token(private_key)
    jwk_dict = _public_key_to_jwk(public_key)

    with patch("whisperx_app.api.auth._get_jwks", return_value={jwk_dict["kid"]: jwk_dict}):
        payload = await validate_token(token)

    assert payload.sub == "user123"
    assert payload.scope == "transcribe"


@pytest.mark.asyncio
async def test_expired_token(rsa_pair, mock_config):
    private_key, public_key = rsa_pair
    token = _make_test_token(private_key, exp_offset=-100)  # already expired
    jwk_dict = _public_key_to_jwk(public_key)

    with patch("whisperx_app.api.auth._get_jwks", return_value={jwk_dict["kid"]: jwk_dict}):
        with pytest.raises(AuthError, match="Token-Validierung"):
            await validate_token(token)


@pytest.mark.asyncio
async def test_wrong_audience(rsa_pair, mock_config):
    private_key, public_key = rsa_pair
    token = _make_test_token(private_key, aud="wrong-client")
    jwk_dict = _public_key_to_jwk(public_key)

    with patch("whisperx_app.api.auth._get_jwks", return_value={jwk_dict["kid"]: jwk_dict}):
        with pytest.raises(AuthError):
            await validate_token(token)


@pytest.mark.asyncio
async def test_wrong_issuer(rsa_pair, mock_config):
    private_key, public_key = rsa_pair
    token = _make_test_token(private_key, iss="https://evil.example.com")
    jwk_dict = _public_key_to_jwk(public_key)

    with patch("whisperx_app.api.auth._get_jwks", return_value={jwk_dict["kid"]: jwk_dict}):
        with pytest.raises(AuthError):
            await validate_token(token)


@pytest.mark.asyncio
async def test_unknown_kid(rsa_pair, mock_config):
    private_key, public_key = rsa_pair
    token = _make_test_token(private_key, kid="known-kid")
    jwk_dict = _public_key_to_jwk(public_key, kid="different-kid")

    with patch("whisperx_app.api.auth._get_jwks", return_value={jwk_dict["kid"]: jwk_dict}):
        with pytest.raises(AuthError, match="(?i)kein Public Key"):
            await validate_token(token)


@pytest.mark.asyncio
async def test_invalid_token_string(mock_config):
    with patch("whisperx_app.api.auth._get_jwks", return_value={}):
        with pytest.raises(AuthError):
            await validate_token("not.a.jwt")


def test_check_scope_passes():
    from whisperx_app.api.auth import check_scope
    from whisperx_app.api.models import TokenPayload
    payload = TokenPayload(sub="u1", scope="transcribe read")
    assert check_scope(payload, "transcribe") is True


def test_check_scope_fails():
    from whisperx_app.api.auth import check_scope
    from whisperx_app.api.models import TokenPayload
    payload = TokenPayload(sub="u1", scope="read")
    assert check_scope(payload, "transcribe") is False


def test_check_scope_empty():
    from whisperx_app.api.auth import check_scope
    from whisperx_app.api.models import TokenPayload
    payload = TokenPayload(sub="u1", scope="")
    assert check_scope(payload, "transcribe") is False
