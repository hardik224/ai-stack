from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from app.library.security import get_bearer_token
from app.services import auth_service


def get_current_user(request: Request) -> dict:
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    return auth_service.authenticate_session_token(token)


def optional_current_user(request: Request) -> dict | None:
    token = get_bearer_token(request)
    if not token:
        return None
    return auth_service.authenticate_session_token(token)


def require_roles(*roles: str) -> Callable:
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
        return current_user

    return dependency
