from fastapi import APIRouter, Depends, Request

from app.controllers import auth_controller
from app.middleware.auth import get_current_user
from app.schemas.auth import ApiKeyCreateRequest, LoginRequest


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    return auth_controller.login(payload=payload, request=request)


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return auth_controller.who_am_i(current_user=current_user)


@router.get("/workspace-summary")
def workspace_summary(current_user: dict = Depends(get_current_user)):
    return auth_controller.get_workspace_summary(current_user=current_user)


@router.post("/api-keys")
def create_api_key(payload: ApiKeyCreateRequest, current_user: dict = Depends(get_current_user)):
    return auth_controller.create_api_key(payload=payload, current_user=current_user)


@router.get("/api-keys")
def list_api_keys(current_user: dict = Depends(get_current_user)):
    return auth_controller.list_api_keys(current_user=current_user)
