from datetime import datetime
from uuid import UUID

from app.library.db import execute, execute_returning, fetch_all, fetch_one


GET_ACTIVE_SESSION = """
SELECT
    s.id AS session_id,
    s.user_id,
    s.expires_at,
    s.last_seen_at,
    u.id,
    u.email,
    u.full_name,
    u.role,
    u.status
FROM auth_sessions s
JOIN users u ON u.id = s.user_id
WHERE
    s.session_token_hash = %s
    AND s.revoked_at IS NULL
    AND s.expires_at > NOW()
    AND u.status = 'active';
"""

INSERT_SESSION = """
INSERT INTO auth_sessions (
    user_id,
    session_token_hash,
    ip_address,
    user_agent,
    expires_at
)
VALUES (%s, %s, %s, %s, %s)
RETURNING id, user_id, expires_at, created_at;
"""

TOUCH_SESSION = """
UPDATE auth_sessions
SET last_seen_at = NOW()
WHERE id = %s;
"""

GET_API_KEY = """
SELECT
    ak.id AS api_key_id,
    ak.user_id,
    ak.name,
    ak.scope,
    ak.expires_at,
    ak.revoked_at,
    u.id,
    u.email,
    u.full_name,
    u.role,
    u.status
FROM api_keys ak
JOIN users u ON u.id = ak.user_id
WHERE
    ak.key_hash = %s
    AND ak.revoked_at IS NULL
    AND (ak.expires_at IS NULL OR ak.expires_at > NOW())
    AND u.status = 'active';
"""

INSERT_API_KEY = """
INSERT INTO api_keys (
    user_id,
    name,
    key_prefix,
    key_hash,
    scope,
    expires_at
)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id, user_id, name, key_prefix, scope, expires_at, created_at;
"""

LIST_API_KEYS = """
SELECT
    id,
    user_id,
    name,
    key_prefix,
    scope,
    expires_at,
    last_used_at,
    created_at
FROM api_keys
WHERE user_id = %s AND revoked_at IS NULL
ORDER BY created_at DESC;
"""

TOUCH_API_KEY = """
UPDATE api_keys
SET last_used_at = NOW()
WHERE id = %s;
"""


def create_session(
    *,
    user_id: UUID,
    session_token_hash: str,
    ip_address: str | None,
    user_agent: str | None,
    expires_at: datetime,
) -> dict | None:
    return execute_returning(
        INSERT_SESSION,
        (str(user_id), session_token_hash, ip_address, user_agent, expires_at),
    )


def get_session_with_user(session_token_hash: str) -> dict | None:
    return fetch_one(GET_ACTIVE_SESSION, (session_token_hash,))


def touch_session(session_id: UUID) -> None:
    execute(TOUCH_SESSION, (str(session_id),))


def create_api_key(
    *,
    user_id: UUID,
    name: str,
    key_prefix: str,
    key_hash: str,
    scope: str,
    expires_at: datetime | None,
) -> dict | None:
    return execute_returning(
        INSERT_API_KEY,
        (str(user_id), name, key_prefix, key_hash, scope, expires_at),
    )


def list_api_keys(user_id: UUID) -> list[dict]:
    return fetch_all(LIST_API_KEYS, (str(user_id),))


def get_api_key_with_user(key_hash: str) -> dict | None:
    return fetch_one(GET_API_KEY, (key_hash,))


def touch_api_key(api_key_id: UUID) -> None:
    execute(TOUCH_API_KEY, (str(api_key_id),))
