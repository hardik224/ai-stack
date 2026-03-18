from datetime import timedelta

from fastapi import HTTPException, Request, status

from app.config.settings import get_settings
from app.library.hashing import generate_api_key, generate_session_token, hash_secret, verify_password
from app.library.security import get_client_ip, utcnow
from app.models import auth_model, user_model
from app.services.activity_service import record_activity



def login(*, payload, request: Request) -> dict:
    user = user_model.get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password.')
    if user['status'] != 'active':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='User account is not active.')

    settings = get_settings()
    raw_token = generate_session_token()
    expires_at = utcnow() + timedelta(hours=settings.auth_session_ttl_hours)
    session = auth_model.create_session(
        user_id=user['id'],
        session_token_hash=hash_secret(raw_token),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get('user-agent'),
        expires_at=expires_at,
    )
    user_model.update_last_login(user['id'])
    record_activity(
        actor_user_id=user['id'],
        activity_type='auth.login',
        target_type='user',
        target_id=user['id'],
        description='User logged in.',
        visibility='foreground',
        metadata={'ip_address': get_client_ip(request)},
    )
    return {
        'token_type': 'bearer',
        'access_token': raw_token,
        'expires_at': session['expires_at'] if session else expires_at,
        'user': _serialize_user(user, auth_type='session'),
    }



def authenticate_session_token(token: str) -> dict:
    session = auth_model.get_session_with_user(hash_secret(token))
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired session.')
    auth_model.touch_session(session['session_id'])
    return _serialize_user(session, auth_type='session')



def authenticate_api_key(api_key: str) -> dict:
    key_record = auth_model.get_api_key_with_user(hash_secret(api_key))
    if not key_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired API key.')
    auth_model.touch_api_key(key_record['api_key_id'])
    return _serialize_user(key_record, auth_type='api_key', api_key_scope=key_record['scope'])



def get_current_identity(current_user: dict) -> dict:
    return current_user



def create_api_key(*, payload, current_user: dict) -> dict:
    target_user_id = payload.user_id or current_user['id']
    if current_user['role'] != 'admin' and str(target_user_id) != str(current_user['id']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Cannot create API keys for other users.')

    target_user = user_model.get_user_by_id(target_user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Target user not found.')

    raw_api_key = generate_api_key()
    expires_at = None
    if payload.expires_in_days:
        expires_at = utcnow() + timedelta(days=payload.expires_in_days)

    api_key = auth_model.create_api_key(
        user_id=target_user_id,
        name=payload.name,
        key_prefix=raw_api_key[:12],
        key_hash=hash_secret(raw_api_key),
        scope=payload.scope,
        expires_at=expires_at,
    )
    record_activity(
        actor_user_id=current_user['id'],
        activity_type='auth.api_key.created',
        target_type='api_key',
        target_id=api_key['id'] if api_key else None,
        description='API key created for chatbot access.',
        visibility='foreground',
        metadata={'user_id': str(target_user_id), 'scope': payload.scope},
    )
    return {
        'api_key': raw_api_key,
        'record': api_key,
        'warning': 'Store this API key now. It will not be returned again.',
    }



def list_api_keys(*, current_user: dict) -> dict:
    return {'items': auth_model.list_api_keys(current_user['id'])}



def _serialize_user(user: dict, *, auth_type: str, api_key_scope: str | None = None) -> dict:
    identity = {
        'id': user['id'],
        'email': user['email'],
        'full_name': user.get('full_name'),
        'role': user['role'],
        'status': user['status'],
        'auth_type': auth_type,
    }
    if api_key_scope:
        identity['api_key_scope'] = api_key_scope
    return identity
