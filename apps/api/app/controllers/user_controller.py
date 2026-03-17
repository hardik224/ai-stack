from app.schemas.user import UserCreateRequest
from app.services import user_service


def create_user(payload: UserCreateRequest, current_user: dict | None):
    return user_service.create_user(payload=payload, current_user=current_user)


def list_users():
    return user_service.list_users()
