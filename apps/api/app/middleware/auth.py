from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from app.library.security import get_api_key_from_request, get_bearer_token
from app.services import auth_service



def get_current_user(request: Request) -> dict:
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing bearer token.')
    return auth_service.authenticate_session_token(token)



def optional_current_user(request: Request) -> dict | None:
    token = get_bearer_token(request)
    if not token:
        return None
    return auth_service.authenticate_session_token(token)



def get_current_identity(request: Request) -> dict:
    token = get_bearer_token(request)
    if token:
        return auth_service.authenticate_session_token(token)

    api_key = get_api_key_from_request(request)
    if api_key:
        return auth_service.authenticate_api_key(api_key)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing authentication credentials.')



def require_roles(*roles: str) -> Callable:
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user['role'] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient permissions.')
        return current_user

    return dependency



def require_chat_access() -> Callable:
    def dependency(current_identity: dict = Depends(get_current_identity)) -> dict:
        if current_identity['role'] not in {'admin', 'internal_user', 'user'}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient permissions.')
        if current_identity.get('auth_type') == 'api_key' and current_identity.get('api_key_scope') != 'chatbot':
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='API key does not have chatbot access.')
        return current_identity

    return dependency
