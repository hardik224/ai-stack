from typing import Any

from app.library.db import execute, fetch_all, to_jsonb


INSERT_ACTIVITY = """
INSERT INTO activity_logs (
    actor_user_id,
    activity_type,
    target_type,
    target_id,
    description,
    visibility,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s);
"""

LIST_RECENT_ACTIVITY = """
SELECT
    a.id,
    a.activity_type,
    a.target_type,
    a.target_id,
    a.description,
    a.visibility,
    a.metadata,
    a.created_at,
    u.id AS actor_user_id,
    u.email AS actor_email,
    u.full_name AS actor_full_name
FROM activity_logs a
LEFT JOIN users u ON u.id = a.actor_user_id
ORDER BY a.created_at DESC
LIMIT %s OFFSET %s;
"""


def create_activity(
    *,
    actor_user_id: str | None,
    activity_type: str,
    target_type: str,
    target_id: str | None,
    description: str,
    visibility: str,
    metadata: dict[str, Any] | None = None,
    conn: Any | None = None,
) -> None:
    execute(
        INSERT_ACTIVITY,
        (
            actor_user_id,
            activity_type,
            target_type,
            target_id,
            description,
            visibility,
            to_jsonb(metadata),
        ),
        conn=conn,
    )


def list_recent_activity(limit: int, offset: int = 0) -> list[dict[str, Any]]:
    return fetch_all(LIST_RECENT_ACTIVITY, (limit, offset))
