from uuid import UUID

from app.library.db import execute, execute_returning, fetch_all, to_jsonb


GET_CHUNKS_BY_IDS = """
SELECT
    c.id,
    c.file_id,
    c.collection_id,
    c.chunk_index,
    c.content,
    c.token_count,
    c.source_type,
    c.page_number,
    c.row_number,
    c.content_hash,
    c.source_metadata,
    f.original_name AS file_name,
    f.content_type,
    f.uploaded_by,
    col.name AS collection_name
FROM chunks c
JOIN files f ON f.id = c.file_id
LEFT JOIN collections col ON col.id = c.collection_id
WHERE c.id = ANY(%s);
"""

INSERT_RETRIEVAL_LOG = """
INSERT INTO retrieval_logs (
    session_id,
    user_id,
    assistant_message_id,
    query_text,
    normalized_query,
    filters,
    top_k,
    score_threshold,
    dedupe_enabled,
    hit_count,
    timings,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id, created_at;
"""



def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    return fetch_all(GET_CHUNKS_BY_IDS, (chunk_ids,))



def create_retrieval_log(
    *,
    session_id: UUID | None,
    user_id: UUID | None,
    assistant_message_id: UUID | None,
    query_text: str,
    normalized_query: str,
    filters: dict | None,
    top_k: int,
    score_threshold: float | None,
    dedupe_enabled: bool,
    hit_count: int,
    timings: dict | None,
    metadata: dict | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        INSERT_RETRIEVAL_LOG,
        (
            str(session_id) if session_id else None,
            str(user_id) if user_id else None,
            str(assistant_message_id) if assistant_message_id else None,
            query_text,
            normalized_query,
            to_jsonb(filters),
            top_k,
            score_threshold,
            dedupe_enabled,
            hit_count,
            to_jsonb(timings),
            to_jsonb(metadata),
        ),
        conn=conn,
    )
