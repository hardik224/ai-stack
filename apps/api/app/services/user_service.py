from fastapi import HTTPException, status

from app.library.hashing import hash_password
from app.models import user_model
from app.services.activity_service import record_activity


def create_user(*, payload, current_user: dict | None) -> dict:
    existing = user_model.get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email address already exists.")

    total_users = user_model.count_users()
    if total_users == 0:
        role = "admin"
    else:
        if not current_user or current_user["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create users.")
        role = payload.role

    created_user = user_model.create_user(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=role,
        status=payload.status,
    )
    record_activity(
        actor_user_id=current_user["id"] if current_user else created_user["id"],
        activity_type="user.created",
        target_type="user",
        target_id=created_user["id"] if created_user else None,
        description=f"User '{payload.email}' created.",
        visibility="foreground",
        metadata={"role": role},
    )
    return created_user


def list_users() -> dict:
    return {"items": user_model.list_users()}
