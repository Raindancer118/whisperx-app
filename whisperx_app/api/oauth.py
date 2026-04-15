"""Volantic OAuth2 / OIDC helpers (authorization code flow with PKCE)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import httpx

VOLANTIC_ISSUER = os.environ.get("VOLANTIC_ISSUER", "https://accounts.volantic.de")
VOLANTIC_CLIENT_ID = os.environ.get("VOLANTIC_CLIENT_ID", "whisperx-app")
VOLANTIC_CLIENT_SECRET = os.environ.get("VOLANTIC_CLIENT_SECRET", "")
APP_URL = os.environ.get("APP_URL", "http://localhost")

AUTHORIZE_URL = f"{VOLANTIC_ISSUER}/oauth/authorize"
TOKEN_URL = f"{VOLANTIC_ISSUER}/api/oauth/token"
USERINFO_URL = f"{VOLANTIC_ISSUER}/api/oauth/userinfo"
REDIRECT_URI = f"{APP_URL}/auth/callback"

SCOPES = "openid email profile"


def build_authorize_url(state: str, code_verifier: str) -> str:
    """Return the full Volantic authorization URL."""
    code_challenge = _pkce_challenge(code_verifier)
    params = {
        "response_type": "code",
        "client_id": VOLANTIC_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str) -> dict:
    """Exchange authorization code for tokens (public PKCE client — no secret)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": VOLANTIC_CLIENT_ID,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_userinfo(access_token: str) -> dict:
    """Fetch user profile from Volantic userinfo endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


# ── PKCE helpers ─────────────────────────────────────────────────────────

def generate_pkce_pair() -> tuple[str, str]:
    """Return (state, code_verifier) — both cryptographically random."""
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(96)
    return state, code_verifier


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    import base64
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ── Session helpers (Redis-backed, signed cookie) ─────────────────────────

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret").encode()
SESSION_TTL = 86400  # 24 hours


def _sign(value: str) -> str:
    mac = hmac.new(SESSION_SECRET, value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{mac}"


def _unsign(signed: str) -> Optional[str]:
    if "." not in signed:
        return None
    value, mac = signed.rsplit(".", 1)
    expected = hmac.new(SESSION_SECRET, value.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    return value


def make_session_cookie(session_id: str) -> str:
    return _sign(session_id)


def verify_session_cookie(cookie: str) -> Optional[str]:
    return _unsign(cookie)
