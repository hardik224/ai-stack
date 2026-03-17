from uuid import UUID

from app.library.db import fetch_all, fetch_one


LIST_ADMIN_USERS = """
SELECT
    u.id,
    u.email,
    u.full_name,
    u.role,
    u.status,
    u.created_at,
    u.last_login_at,
    COALESCE(f.file_count, 0) AS file_count,
    COALESCE(f.total_uploaded_bytes, 0) AS total_uploaded_bytes,
    COALESCE(j.job_count, 0) AS job_count,
    COALESCE(c.chat_session_count, 0) AS chat_session_count,
    COALESCE(c.message_count, 0) AS message_count
FROM users u
LEFT JOIN (
    SELECT
        uploaded_by AS user_id,
        COUNT(*) AS file_count,
        COALESCE(SUM(size_bytes), 0) AS total_uploaded_bytes
    FROM files
    GROUP BY uploaded_by
) f ON f.user_id = u.id
LEFT JOIN (
    SELECT
        created_by AS user_id,
        COUNT(*) AS job_count
    FROM ingestion_jobs
    GROUP BY created_by
) j ON j.user_id = u.id
LEFT JOIN (
    SELECT
        cs.user_id,
        COUNT(DISTINCT cs.id) AS chat_session_count,
        COUNT(cm.id) AS message_count
    FROM chat_sessions cs
    LEFT JOIN chat_messages cm ON cm.session_id = cs.id
    GROUP BY cs.user_id
) c ON c.user_id = u.id
ORDER BY u.created_at DESC
LIMIT %s OFFSET %s;
"""

GET_ADMIN_USER = """
SELECT
    u.id,
    u.email,
    u.full_name,
    u.role,
    u.status,
    u.created_at,
    u.updated_at,
    u.last_login_at,
    COALESCE(f.file_count, 0) AS file_count,
    COALESCE(f.total_uploaded_bytes, 0) AS total_uploaded_bytes,
    COALESCE(j.job_count, 0) AS job_count,
    COALESCE(j.completed_jobs, 0) AS completed_jobs,
    COALESCE(j.failed_jobs, 0) AS failed_jobs,
    COALESCE(c.chat_session_count, 0) AS chat_session_count,
    COALESCE(c.message_count, 0) AS message_count
FROM users u
LEFT JOIN (
    SELECT
        uploaded_by AS user_id,
        COUNT(*) AS file_count,
        COALESCE(SUM(size_bytes), 0) AS total_uploaded_bytes
    FROM files
    GROUP BY uploaded_by
) f ON f.user_id = u.id
LEFT JOIN (
    SELECT
        created_by AS user_id,
        COUNT(*) AS job_count,
        COUNT(*) FILTER (WHERE status = 'completed') AS completed_jobs,
        COUNT(*) FILTER (WHERE status = 'failed') AS failed_jobs
    FROM ingestion_jobs
    GROUP BY created_by
) j ON j.user_id = u.id
LEFT JOIN (
    SELECT
        cs.user_id,
        COUNT(DISTINCT cs.id) AS chat_session_count,
        COUNT(cm.id) AS message_count
    FROM chat_sessions cs
    LEFT JOIN chat_messages cm ON cm.session_id = cs.id
    GROUP BY cs.user_id
) c ON c.user_id = u.id
WHERE u.id = %s;
"""

LIST_UPLOADS = """
SELECT
    f.id,
    f.original_name,
    f.content_type,
    f.size_bytes,
    f.created_at,
    f.minio_bucket,
    f.minio_object_key,
    c.id AS collection_id,
    c.name AS collection_name,
    u.id AS uploaded_by_user_id,
    u.email AS uploaded_by_email,
    u.full_name AS uploaded_by_full_name,
    j.id AS latest_job_id,
    j.status AS latest_job_status,
    j.current_stage AS latest_job_stage,
    j.progress_percent AS latest_job_progress
FROM files f
JOIN users u ON u.id = f.uploaded_by
LEFT JOIN collections c ON c.id = f.collection_id
LEFT JOIN LATERAL (
    SELECT
        ij.id,
        ij.status,
        ij.current_stage,
        ij.progress_percent
    FROM ingestion_jobs ij
    WHERE ij.file_id = f.id
    ORDER BY ij.created_at DESC
    LIMIT 1
) j ON TRUE
ORDER BY f.created_at DESC
LIMIT %s OFFSET %s;
"""

UPLOAD_SUMMARY = """
SELECT
    u.id AS user_id,
    u.email,
    u.full_name,
    COUNT(f.id) AS file_count,
    COALESCE(SUM(f.size_bytes), 0) AS total_uploaded_bytes,
    MAX(f.created_at) AS last_upload_at
FROM users u
LEFT JOIN files f ON f.uploaded_by = u.id
GROUP BY u.id, u.email, u.full_name
ORDER BY total_uploaded_bytes DESC, file_count DESC, u.created_at ASC;
"""

LIST_CHAT_SESSIONS = """
SELECT
    cs.id,
    cs.user_id,
    u.email AS user_email,
    u.full_name AS user_full_name,
    cs.title,
    cs.status,
    cs.collection_id,
    cs.created_at,
    cs.last_message_at,
    COUNT(cm.id) AS message_count
FROM chat_sessions cs
JOIN users u ON u.id = cs.user_id
LEFT JOIN chat_messages cm ON cm.session_id = cs.id
GROUP BY cs.id, u.email, u.full_name
ORDER BY cs.created_at DESC
LIMIT %s OFFSET %s;
"""

GET_CHAT_SESSION = """
SELECT
    cs.id,
    cs.user_id,
    u.email AS user_email,
    u.full_name AS user_full_name,
    cs.title,
    cs.status,
    cs.collection_id,
    cs.created_at,
    cs.updated_at,
    cs.last_message_at,
    cs.metadata
FROM chat_sessions cs
JOIN users u ON u.id = cs.user_id
WHERE cs.id = %s;
"""

LIST_CHAT_MESSAGES = """
SELECT
    cm.id,
    cm.role,
    cm.content,
    cm.token_count,
    cm.metadata,
    cm.created_at,
    cm.user_id,
    u.email AS user_email
FROM chat_messages cm
LEFT JOIN users u ON u.id = cm.user_id
WHERE cm.session_id = %s
ORDER BY cm.created_at ASC;
"""

DASHBOARD_SUMMARY = """
SELECT
    (SELECT COUNT(*) FROM users) AS total_users,
    (SELECT COUNT(*) FROM users WHERE role = 'admin') AS admin_users,
    (SELECT COUNT(*) FROM users WHERE role = 'internal_user') AS internal_users,
    (SELECT COUNT(*) FROM users WHERE role = 'user') AS standard_users,
    (SELECT COUNT(*) FROM collections) AS total_collections,
    (SELECT COUNT(*) FROM files) AS total_files,
    (SELECT COALESCE(SUM(size_bytes), 0) FROM files) AS total_uploaded_bytes,
    (SELECT COUNT(*) FROM ingestion_jobs) AS total_jobs,
    (SELECT COUNT(*) FROM ingestion_jobs WHERE status = 'queued') AS queued_jobs,
    (SELECT COUNT(*) FROM ingestion_jobs WHERE status = 'processing') AS processing_jobs,
    (SELECT COUNT(*) FROM ingestion_jobs WHERE status = 'completed') AS completed_jobs,
    (SELECT COUNT(*) FROM ingestion_jobs WHERE status = 'failed') AS failed_jobs,
    (SELECT COUNT(*) FROM background_tasks WHERE status = 'running') AS running_background_processes,
    (SELECT COUNT(*) FROM chat_sessions) AS total_chat_sessions,
    (SELECT COUNT(*) FROM chat_messages) AS total_chat_messages;
"""


def list_admin_users(limit: int, offset: int) -> list[dict]:
    return fetch_all(LIST_ADMIN_USERS, (limit, offset))


def get_admin_user(user_id: UUID) -> dict | None:
    return fetch_one(GET_ADMIN_USER, (str(user_id),))


def list_uploads(limit: int, offset: int) -> list[dict]:
    return fetch_all(LIST_UPLOADS, (limit, offset))


def get_upload_summary() -> list[dict]:
    return fetch_all(UPLOAD_SUMMARY)


def list_chat_sessions(limit: int, offset: int) -> list[dict]:
    return fetch_all(LIST_CHAT_SESSIONS, (limit, offset))


def get_chat_session(session_id: UUID) -> dict | None:
    return fetch_one(GET_CHAT_SESSION, (str(session_id),))


def list_chat_messages(session_id: UUID) -> list[dict]:
    return fetch_all(LIST_CHAT_MESSAGES, (str(session_id),))


def get_dashboard_summary() -> dict:
    return fetch_one(DASHBOARD_SUMMARY) or {}
