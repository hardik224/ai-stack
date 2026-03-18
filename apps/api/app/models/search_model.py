from app.library.db import fetch_all


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
WHERE c.id = ANY(%s)
ORDER BY c.chunk_index ASC;
"""



def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    return fetch_all(GET_CHUNKS_BY_IDS, (chunk_ids,))
