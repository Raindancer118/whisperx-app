"""FastAPI dependencies for web (session-cookie) authentication."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from whisperx_app.api import session_store
from whisperx_app.api.oauth import verify_session_cookie


class CurrentUser:
    def __init__(self, user_id: str, email: str, name: str):
        self.user_id = user_id
        self.email = email
        self.name = name


async def get_current_user(
    wx_session: str | None = Cookie(default=None),
) -> CurrentUser:
    if not wx_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")

    session_id = verify_session_cookie(wx_session)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Session")

    raw = await session_store.get(f"session:{session_id}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session abgelaufen")

    data = json.loads(raw)
    return CurrentUser(
        user_id=data.get("user_id", ""),
        email=data.get("email", ""),
        name=data.get("name", ""),
    )


WebUser = Annotated[CurrentUser, Depends(get_current_user)]
