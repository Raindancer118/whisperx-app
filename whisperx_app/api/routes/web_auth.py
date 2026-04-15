"""Volantic OAuth2 login/callback routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import RedirectResponse

from whisperx_app.api import session_store
from whisperx_app.api.oauth import (
    SESSION_TTL,
    build_authorize_url,
    exchange_code,
    generate_pkce_pair,
    get_userinfo,
    make_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])

APP_URL = __import__("os").environ.get("APP_URL", "http://localhost")


@router.get("/login")
async def login(response: Response) -> RedirectResponse:
    """Redirect user to Volantic authorization page."""
    state, code_verifier = generate_pkce_pair()
    # Store state+verifier in Redis keyed by state (TTL 10 min)
    await session_store.set(
        f"pkce:{state}",
        json.dumps({"code_verifier": code_verifier}),
        ttl=600,
    )
    url = build_authorize_url(state, code_verifier)
    return RedirectResponse(url, status_code=302)


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle OAuth2 callback: exchange code, create session, redirect."""
    if error or not code or not state:
        return RedirectResponse(f"{APP_URL}/?error=auth_failed", status_code=302)

    # Retrieve code_verifier
    raw = await session_store.get(f"pkce:{state}")
    if not raw:
        return RedirectResponse(f"{APP_URL}/?error=invalid_state", status_code=302)
    await session_store.delete(f"pkce:{state}")
    code_verifier = json.loads(raw)["code_verifier"]

    try:
        tokens = await exchange_code(code, code_verifier)
        userinfo = await get_userinfo(tokens["access_token"])
    except Exception:
        return RedirectResponse(f"{APP_URL}/?error=token_exchange_failed", status_code=302)

    user_id = userinfo.get("sub") or userinfo.get("id") or ""
    user_email = userinfo.get("email") or ""
    user_name = userinfo.get("name") or userinfo.get("preferred_username") or user_email

    session_data = {
        "user_id": user_id,
        "email": user_email,
        "name": user_name,
        "access_token": tokens.get("access_token", ""),
    }

    import secrets
    session_id = secrets.token_urlsafe(32)
    await session_store.set(
        f"session:{session_id}",
        json.dumps(session_data),
        ttl=SESSION_TTL,
    )

    cookie_value = make_session_cookie(session_id)
    redirect = RedirectResponse(f"{APP_URL}/dashboard", status_code=302)
    redirect.set_cookie(
        "wx_session",
        cookie_value,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL,
        secure=APP_URL.startswith("https"),
    )
    return redirect


@router.post("/logout")
async def logout(
    response: Response,
    wx_session: str | None = Cookie(default=None),
) -> dict:
    """Clear session cookie and Redis session data."""
    if wx_session:
        from whisperx_app.api.oauth import verify_session_cookie
        session_id = verify_session_cookie(wx_session)
        if session_id:
            await session_store.delete(f"session:{session_id}")
    response.delete_cookie("wx_session")
    return {"ok": True}
