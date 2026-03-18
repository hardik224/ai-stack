from uuid import UUID

from app.library.db import execute_returning, fetch_all, to_jsonb


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

SEARCH_KEYWORD_CHUNKS = """
WITH ranked AS (
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
        col.name AS collection_name,
        ts_rank_cd(
            to_tsvector('simple', COALESCE(c.content, '')),
            websearch_to_tsquery('simple', %s)
        ) AS simple_rank,
        ts_rank_cd(
            to_tsvector('english', COALESCE(c.content, '')),
            websearch_to_tsquery('english', %s)
        ) AS english_rank,
        similarity(COALESCE(f.original_name, ''), %s) AS filename_similarity,
        CASE WHEN lower(COALESCE(f.original_name, '')) LIKE ('%%' || lower(%s) || '%%') THEN 1 ELSE 0 END AS filename_match,
        CASE WHEN lower(COALESCE(c.content, '')) LIKE ('%%' || lower(%s) || '%%') THEN 1 ELSE 0 END AS phrase_match
    FROM chunks c
    JOIN files f ON f.id = c.file_id
    LEFT JOIN collections col ON col.id = c.collection_id
    WHERE (%s::uuid IS NULL OR c.collection_id = %s::uuid)
      AND (%s::uuid IS NULL OR c.file_id = %s::uuid)
      AND (%s::text IS NULL OR c.source_type = %s::text)
      AND (
          to_tsvector('simple', COALESCE(c.content, '')) @@ websearch_to_tsquery('simple', %s)
          OR to_tsvector('english', COALESCE(c.content, '')) @@ websearch_to_tsquery('english', %s)
          OR similarity(COALESCE(f.original_name, ''), %s) > 0.12
          OR lower(COALESCE(c.content, '')) LIKE ('%%' || lower(%s) || '%%')
          OR lower(COALESCE(f.original_name, '')) LIKE ('%%' || lower(%s) || '%%')
      )
)
SELECT
    *,
    (
        (simple_rank * 1.15) +
        (english_rank * 0.95) +
        (filename_similarity * 0.35) +
        (filename_match * 0.30) +
        (phrase_match * 0.20)
    ) AS keyword_rank_score
FROM ranked
ORDER BY keyword_rank_score DESC, chunk_index ASC
LIMIT %s;
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



def search_keyword_chunks(
    *,
    query_text: str,
    collection_id: UUID | None,
    file_id: UUID | None,
    source_type: str | None,
    limit: int,
) -> list[dict]:
    return fetch_all(
        SEARCH_KEYWORD_CHUNKS,
        (
            query_text,
            query_text,
            query_text,
            query_text,
            query_text,
            str(collection_id) if collection_id else None,
            str(collection_id) if collection_id else None,
            str(file_id) if file_id else None,
            str(file_id) if file_id else None,
            source_type,
            source_type,
            query_text,
            query_text,
            query_text,
            query_text,
            query_text,
            limit,
        ),
    )



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
