"""JWT authentication via Volantic Auth (RS256 / JWKS).

Fetches the JWKS from https://accounts.volantic.de/api/.well-known/jwks.json,
caches the keys for 1 hour, and validates Bearer tokens against them.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode

from whisperx_app.api.models import TokenPayload
from whisperx_app.config import load_config

# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600  # re-fetch every hour


async def _get_jwks() -> dict[str, Any]:
    """Return the cached JWKS key set, refreshing if TTL has expired."""
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    cfg = load_config()
    jwks_url = f"{cfg.volantic_issuer}/api/.well-known/jwks.json"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        data = response.json()

    # Index by kid for O(1) lookup
    _jwks_cache = {key["kid"]: key for key in data.get("keys", [])}
    _jwks_fetched_at = now
    return _jwks_cache


async def _get_public_key(token: str) -> Any:
    """Extract the public key matching the token's kid header."""
    from jose.backends import RSAKey

    # Decode header without verification to get kid
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise AuthError(f"Ungültiger Token-Header: {e}")

    alg = header.get("alg", "")
    if alg != "RS256":
        raise AuthError(f"Ungültiger Algorithmus: {alg!r} (erwartet RS256)")

    kid = header.get("kid")
    if not kid:
        raise AuthError("Token-Header enthält kein 'kid'")

    keys = await _get_jwks()
    key_data = keys.get(kid)

    if not key_data:
        # kid not in cache → maybe keys were rotated; refresh once
        _invalidate_jwks_cache()
        keys = await _get_jwks()
        key_data = keys.get(kid)

    if not key_data:
        raise AuthError(f"Kein Public Key für kid={kid!r} gefunden")

    return jwk.construct(key_data)


def _invalidate_jwks_cache() -> None:
    global _jwks_fetched_at
    _jwks_fetched_at = 0.0


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Raised when JWT validation fails."""
    pass


async def validate_token(token: str) -> TokenPayload:
    """Validate a Volantic Auth Bearer token and return its payload.

    Validates:
    - Signature using RS256 + JWKS public key
    - Expiry (python-jose checks this automatically)
    - Issuer matches configured Volantic Auth issuer
    - Audience matches configured client ID

    Raises:
        AuthError: on any validation failure
    """
    cfg = load_config()
    key = await _get_public_key(token)

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=cfg.volantic_client_id,
            issuer=cfg.volantic_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as e:
        raise AuthError(f"Token-Validierung fehlgeschlagen: {e}")

    return TokenPayload(**payload)


def check_scope(payload: TokenPayload, required_scope: str) -> bool:
    """Return True if the token payload contains the required scope."""
    scopes = payload.scope.split() if payload.scope else []
    return required_scope in scopes
