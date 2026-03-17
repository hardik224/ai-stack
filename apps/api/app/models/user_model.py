from uuid import UUID

from app.library.db import execute, execute_returning, fetch_all, fetch_one


COUNT_USERS = "SELECT COUNT(*) AS count FROM users;"

GET_USER_BY_EMAIL = """
SELECT
    id,
    email,
    full_name,
    password_hash,
    role,
    status,
    last_login_at,
    created_at,
    updated_at
FROM users
WHERE lower(email) = lower(%s);
"""

GET_USER_BY_ID = """
SELECT
    id,
    email,
    full_name,
    role,
    status,
    last_login_at,
    created_at,
    updated_at
FROM users
WHERE id = %s;
"""

INSERT_USER = """
INSERT INTO users (
    email,
    full_name,
    password_hash,
    role,
    status
)
VALUES (%s, %s, %s, %s, %s)
RETURNING
    id,
    email,
    full_name,
    role,
    status,
    last_login_at,
    created_at,
    updated_at;
"""

LIST_USERS = """
SELECT
    id,
    email,
    full_name,
    role,
    status,
    last_login_at,
    created_at,
    updated_at
FROM users
ORDER BY created_at DESC;
"""

UPDATE_LAST_LOGIN = """
UPDATE users
SET last_login_at = NOW()
WHERE id = %s;
"""


def count_users() -> int:
    row = fetch_one(COUNT_USERS)
    return int(row["count"]) if row else 0


def get_user_by_email(email: str) -> dict | None:
    return fetch_one(GET_USER_BY_EMAIL, (email,))


def get_user_by_id(user_id: UUID) -> dict | None:
    return fetch_one(GET_USER_BY_ID, (str(user_id),))


def create_user(
    *,
    email: str,
    full_name: str,
    password_hash: str,
    role: str,
    status: str,
) -> dict | None:
    return execute_returning(
        INSERT_USER,
        (email, full_name, password_hash, role, status),
    )


def list_users() -> list[dict]:
    return fetch_all(LIST_USERS)


def update_last_login(user_id: UUID) -> None:
    execute(UPDATE_LAST_LOGIN, (str(user_id),))
