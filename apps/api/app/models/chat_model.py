from uuid import UUID

from app.library.db import execute, execute_returning, fetch_all, fetch_one, to_jsonb


CREATE_CHAT_SESSION = """
INSERT INTO chat_sessions (
    user_id,
    collection_id,
    title,
    status,
    metadata,
    last_message_at
)
VALUES (%s, %s, %s, 'active', %s, NOW())
RETURNING id, user_id, collection_id, title, status, metadata, last_message_at, created_at, updated_at;
"""

GET_CHAT_SESSION = """
SELECT
    cs.id,
    cs.user_id,
    cs.collection_id,
    cs.title,
    cs.status,
    cs.metadata,
    cs.last_message_at,
    cs.created_at,
    cs.updated_at,
    u.email AS user_email,
    u.full_name AS user_full_name,
    COALESCE(stats.message_count, 0) AS message_count,
    COALESCE(stats.assistant_message_count, 0) AS assistant_message_count,
    COALESCE(stats.failed_message_count, 0) AS failed_message_count
FROM chat_sessions cs
JOIN users u ON u.id = cs.user_id
LEFT JOIN (
    SELECT
        session_id,
        COUNT(*) AS message_count,
        COUNT(*) FILTER (WHERE role = 'assistant') AS assistant_message_count,
        COUNT(*) FILTER (WHERE role = 'assistant' AND status = 'failed') AS failed_message_count
    FROM chat_messages
    GROUP BY session_id
) stats ON stats.session_id = cs.id
WHERE cs.id = %s;
"""

LIST_CHAT_SESSIONS_FOR_USER = """
SELECT
    cs.id,
    cs.user_id,
    cs.collection_id,
    cs.title,
    cs.status,
    cs.metadata,
    cs.last_message_at,
    cs.created_at,
    cs.updated_at,
    COALESCE(stats.message_count, 0) AS message_count,
    COALESCE(stats.assistant_message_count, 0) AS assistant_message_count,
    COALESCE(stats.failed_message_count, 0) AS failed_message_count,
    last_message.role AS last_message_role,
    last_message.content AS last_message_content,
    last_message.status AS last_message_status
FROM chat_sessions cs
LEFT JOIN (
    SELECT
        session_id,
        COUNT(*) AS message_count,
        COUNT(*) FILTER (WHERE role = 'assistant') AS assistant_message_count,
        COUNT(*) FILTER (WHERE role = 'assistant' AND status = 'failed') AS failed_message_count
    FROM chat_messages
    GROUP BY session_id
) stats ON stats.session_id = cs.id
LEFT JOIN LATERAL (
    SELECT role, content, status
    FROM chat_messages cm
    WHERE cm.session_id = cs.id
    ORDER BY cm.created_at DESC
    LIMIT 1
) last_message ON TRUE
WHERE cs.user_id = %s
ORDER BY cs.updated_at DESC
LIMIT %s OFFSET %s;
"""

CREATE_CHAT_MESSAGE = """
INSERT INTO chat_messages (
    session_id,
    user_id,
    role,
    content,
    token_count,
    metadata,
    status,
    error_message
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id, session_id, user_id, role, content, token_count, metadata, status, error_message, created_at, updated_at;
"""

UPDATE_CHAT_MESSAGE = """
UPDATE chat_messages
SET
    content = %s,
    token_count = %s,
    metadata = %s,
    status = %s,
    error_message = %s,
    updated_at = NOW()
WHERE id = %s
RETURNING id, session_id, user_id, role, content, token_count, metadata, status, error_message, created_at, updated_at;
"""

LIST_MESSAGES_FOR_SESSION = """
SELECT
    cm.id,
    cm.session_id,
    cm.user_id,
    cm.role,
    cm.content,
    cm.token_count,
    cm.metadata,
    cm.status,
    cm.error_message,
    cm.created_at,
    cm.updated_at,
    u.email AS user_email,
    COALESCE(src.citation_count, 0) AS citation_count
FROM chat_messages cm
LEFT JOIN users u ON u.id = cm.user_id
LEFT JOIN (
    SELECT message_id, COUNT(*) AS citation_count
    FROM chat_message_sources
    GROUP BY message_id
) src ON src.message_id = cm.id
WHERE cm.session_id = %s
ORDER BY cm.created_at ASC;
"""

LIST_RECENT_MESSAGES_FOR_SESSION = """
SELECT
    cm.id,
    cm.session_id,
    cm.user_id,
    cm.role,
    cm.content,
    cm.token_count,
    cm.metadata,
    cm.status,
    cm.error_message,
    cm.created_at,
    cm.updated_at
FROM chat_messages cm
WHERE cm.session_id = %s
ORDER BY cm.created_at DESC
LIMIT %s;
"""

UPSERT_SESSION_ACTIVITY = """
UPDATE chat_sessions
SET
    last_message_at = NOW(),
    updated_at = NOW(),
    collection_id = COALESCE(%s, collection_id),
    metadata = COALESCE(metadata, '{}'::jsonb) || %s
WHERE id = %s;
"""

UPDATE_SESSION_TITLE = """
UPDATE chat_sessions
SET title = %s, updated_at = NOW()
WHERE id = %s AND (title = 'New Chat' OR title IS NULL OR title = '');
"""

INSERT_CHAT_MESSAGE_SOURCE = """
INSERT INTO chat_message_sources (
    message_id,
    chunk_id,
    file_id,
    citation_label,
    rank,
    score,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s);
"""

LIST_MESSAGE_SOURCES_FOR_SESSION = """
SELECT
    cms.id,
    cms.message_id,
    cms.chunk_id,
    cms.file_id,
    cms.citation_label,
    cms.rank,
    cms.score,
    cms.metadata,
    cms.created_at,
    ch.page_number,
    ch.row_number,
    f.original_name AS file_name
FROM chat_message_sources cms
JOIN chat_messages cm ON cm.id = cms.message_id
JOIN chunks ch ON ch.id = cms.chunk_id
JOIN files f ON f.id = cms.file_id
WHERE cm.session_id = %s
ORDER BY cms.message_id ASC, cms.rank ASC;
"""



def create_chat_session(*, user_id: UUID, collection_id: UUID | None, title: str, metadata: dict | None, conn=None) -> dict | None:
    return execute_returning(
        CREATE_CHAT_SESSION,
        (str(user_id), str(collection_id) if collection_id else None, title, to_jsonb(metadata)),
        conn=conn,
    )



def get_chat_session(session_id: UUID, conn=None) -> dict | None:
    return fetch_one(GET_CHAT_SESSION, (str(session_id),), conn=conn)



def list_chat_sessions_for_user(*, user_id: UUID, limit: int, offset: int, conn=None) -> list[dict]:
    return fetch_all(LIST_CHAT_SESSIONS_FOR_USER, (str(user_id), limit, offset), conn=conn)



def create_chat_message(
    *,
    session_id: UUID,
    user_id: UUID | None,
    role: str,
    content: str,
    token_count: int | None,
    metadata: dict | None,
    status: str,
    error_message: str | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        CREATE_CHAT_MESSAGE,
        (
            str(session_id),
            str(user_id) if user_id else None,
            role,
            content,
            token_count,
            to_jsonb(metadata),
            status,
            error_message,
        ),
        conn=conn,
    )



def update_chat_message(
    *,
    message_id: UUID,
    content: str,
    token_count: int | None,
    metadata: dict | None,
    status: str,
    error_message: str | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        UPDATE_CHAT_MESSAGE,
        (content, token_count, to_jsonb(metadata), status, error_message, str(message_id)),
        conn=conn,
    )



def list_messages_for_session(session_id: UUID, conn=None) -> list[dict]:
    return fetch_all(LIST_MESSAGES_FOR_SESSION, (str(session_id),), conn=conn)



def list_recent_messages_for_session(session_id: UUID, limit: int, conn=None) -> list[dict]:
    return fetch_all(LIST_RECENT_MESSAGES_FOR_SESSION, (str(session_id), limit), conn=conn)



def touch_session(*, session_id: UUID, collection_id: UUID | None, metadata: dict | None, conn=None) -> None:
    execute(UPSERT_SESSION_ACTIVITY, (str(collection_id) if collection_id else None, to_jsonb(metadata), str(session_id)), conn=conn)



def maybe_update_session_title(*, session_id: UUID, title: str, conn=None) -> None:
    execute(UPDATE_SESSION_TITLE, (title, str(session_id)), conn=conn)



def create_message_source(
    *,
    message_id: UUID,
    chunk_id: UUID,
    file_id: UUID,
    citation_label: str,
    rank: int,
    score: float,
    metadata: dict | None,
    conn=None,
) -> None:
    execute(
        INSERT_CHAT_MESSAGE_SOURCE,
        (
            str(message_id),
            str(chunk_id),
            str(file_id),
            citation_label,
            rank,
            score,
            to_jsonb(metadata),
        ),
        conn=conn,
    )



def list_message_sources_for_session(session_id: UUID, conn=None) -> list[dict]:
    return fetch_all(LIST_MESSAGE_SOURCES_FOR_SESSION, (str(session_id),), conn=conn)
