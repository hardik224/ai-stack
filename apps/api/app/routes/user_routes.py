from fastapi import APIRouter, Depends

from app.controllers import user_controller
from app.middleware.auth import optional_current_user, require_roles
from app.schemas.user import UserCreateRequest


router = APIRouter(tags=["users"])


@router.post("/users")
def create_user(payload: UserCreateRequest, current_user: dict | None = Depends(optional_current_user)):
    return user_controller.create_user(payload=payload, current_user=current_user)


@router.get("/users")
def list_users(_: dict = Depends(require_roles("admin"))):
    return user_controller.list_users()
