from fastapi import Request

from app.schemas.auth import ApiKeyCreateRequest, LoginRequest
from app.services import auth_service


def login(payload: LoginRequest, request: Request):
    return auth_service.login(payload=payload, request=request)


def who_am_i(current_user: dict):
    return auth_service.get_current_identity(current_user)


def create_api_key(payload: ApiKeyCreateRequest, current_user: dict):
    return auth_service.create_api_key(payload=payload, current_user=current_user)


def list_api_keys(current_user: dict):
    return auth_service.list_api_keys(current_user=current_user)


def get_workspace_summary(current_user: dict):
    return auth_service.get_workspace_summary(current_user=current_user)
