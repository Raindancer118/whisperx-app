"""FastAPI dependency injectors for authentication and scope checking."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from whisperx_app.api.auth import AuthError, check_scope, validate_token
from whisperx_app.api.models import TokenPayload

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> TokenPayload:
    """Validate the Bearer JWT and return the decoded token payload."""
    try:
        return await validate_token(credentials.credentials)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_scope(scope: str):
    """Return a FastAPI dependency that checks for a specific scope."""
    async def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not check_scope(user, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Erforderlicher Scope fehlt: {scope!r}",
            )
        return user

    return _check
