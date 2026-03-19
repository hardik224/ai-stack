from uuid import UUID

from app.library.db import fetch_one


GET_WORKSPACE_SUMMARY = """
SELECT
    u.id AS user_id,
    u.email,
    u.full_name,
    u.role,
    COALESCE(f.file_count, 0) AS file_count,
    COALESCE(f.total_uploaded_bytes, 0) AS total_uploaded_bytes,
    f.last_upload_at,
    COALESCE(j.job_count, 0) AS job_count,
    COALESCE(j.queued_jobs, 0) AS queued_jobs,
    COALESCE(j.processing_jobs, 0) AS processing_jobs,
    COALESCE(j.completed_jobs, 0) AS completed_jobs,
    COALESCE(j.failed_jobs, 0) AS failed_jobs,
    COALESCE(c.chat_session_count, 0) AS chat_session_count,
    COALESCE(c.message_count, 0) AS message_count,
    COALESCE(c.assistant_message_count, 0) AS assistant_message_count,
    COALESCE(c.failed_message_count, 0) AS failed_message_count,
    c.last_chat_at
FROM users u
LEFT JOIN (
    SELECT
        uploaded_by AS user_id,
        COUNT(*) AS file_count,
        COALESCE(SUM(size_bytes), 0) AS total_uploaded_bytes,
        MAX(created_at) AS last_upload_at
    FROM files
    GROUP BY uploaded_by
) f ON f.user_id = u.id
LEFT JOIN (
    SELECT
        created_by AS user_id,
        COUNT(*) AS job_count,
        COUNT(*) FILTER (WHERE status = 'queued') AS queued_jobs,
        COUNT(*) FILTER (WHERE status = 'processing') AS processing_jobs,
        COUNT(*) FILTER (WHERE status = 'completed') AS completed_jobs,
        COUNT(*) FILTER (WHERE status = 'failed') AS failed_jobs
    FROM ingestion_jobs
    GROUP BY created_by
) j ON j.user_id = u.id
LEFT JOIN (
    SELECT
        cs.user_id,
        COUNT(DISTINCT cs.id) AS chat_session_count,
        COUNT(cm.id) AS message_count,
        COUNT(cm.id) FILTER (WHERE cm.role = 'assistant') AS assistant_message_count,
        COUNT(cm.id) FILTER (WHERE cm.role = 'assistant' AND cm.status = 'failed') AS failed_message_count,
        MAX(cm.created_at) AS last_chat_at
    FROM chat_sessions cs
    LEFT JOIN chat_messages cm ON cm.session_id = cs.id
    GROUP BY cs.user_id
) c ON c.user_id = u.id
WHERE u.id = %s;
"""


def get_workspace_summary(user_id: UUID) -> dict | None:
    return fetch_one(GET_WORKSPACE_SUMMARY, (str(user_id),))
