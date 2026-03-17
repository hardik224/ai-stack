from uuid import UUID

from app.models import activity_model


def record_activity(
    *,
    actor_user_id: UUID | None,
    activity_type: str,
    target_type: str,
    target_id: UUID | None,
    description: str,
    visibility: str,
    metadata: dict | None = None,
    conn=None,
) -> None:
    activity_model.create_activity(
        actor_user_id=str(actor_user_id) if actor_user_id else None,
        activity_type=activity_type,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        description=description,
        visibility=visibility,
        metadata=metadata,
        conn=conn,
    )
