from uuid import UUID

from app.library.db import execute_returning, fetch_all, fetch_one, to_jsonb


INSERT_FILE = """
INSERT INTO files (
    id,
    collection_id,
    uploaded_by,
    original_name,
    stored_name,
    content_type,
    size_bytes,
    minio_bucket,
    minio_object_key,
    checksum_sha256,
    source_type,
    ingestion_status,
    last_ingested_job_id,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING
    id,
    collection_id,
    uploaded_by,
    original_name,
    stored_name,
    content_type,
    size_bytes,
    minio_bucket,
    minio_object_key,
    checksum_sha256,
    source_type,
    ingestion_status,
    last_ingested_job_id,
    metadata,
    created_at;
"""

GET_FILE = """
SELECT
    f.id,
    f.collection_id,
    f.uploaded_by,
    f.original_name,
    f.stored_name,
    f.content_type,
    f.size_bytes,
    f.minio_bucket,
    f.minio_object_key,
    f.checksum_sha256,
    f.source_type,
    f.page_count,
    f.row_count,
    f.total_chunks,
    f.indexed_chunks,
    f.ingestion_status,
    f.last_ingested_job_id,
    f.last_ingested_at,
    f.error_message,
    f.metadata,
    f.created_at,
    f.updated_at,
    c.name AS collection_name,
    u.email AS uploaded_by_email,
    u.full_name AS uploaded_by_full_name,
    j.id AS latest_job_id,
    j.status AS latest_job_status,
    j.current_stage AS latest_job_stage,
    j.progress_percent AS latest_job_progress,
    j.total_chunks AS latest_job_total_chunks,
    j.processed_chunks AS latest_job_processed_chunks,
    j.indexed_chunks AS latest_job_indexed_chunks,
    j.progress_message AS latest_job_progress_message,
    j.started_at AS latest_job_started_at,
    j.completed_at AS latest_job_completed_at,
    j.failed_at AS latest_job_failed_at,
    j.error_message AS latest_job_error_message
FROM files f
LEFT JOIN collections c ON c.id = f.collection_id
JOIN users u ON u.id = f.uploaded_by
LEFT JOIN LATERAL (
    SELECT
        ij.id,
        ij.status,
        ij.current_stage,
        ij.progress_percent,
        ij.total_chunks,
        ij.processed_chunks,
        ij.indexed_chunks,
        ij.progress_message,
        ij.started_at,
        ij.completed_at,
        ij.failed_at,
        ij.error_message
    FROM ingestion_jobs ij
    WHERE ij.file_id = f.id
    ORDER BY ij.created_at DESC
    LIMIT 1
) j ON TRUE
WHERE f.id = %s;
"""

LIST_FILES_FOR_ADMIN = """
SELECT
    f.id,
    f.collection_id,
    f.uploaded_by,
    f.original_name,
    f.content_type,
    f.size_bytes,
    f.source_type,
    f.total_chunks,
    f.indexed_chunks,
    f.ingestion_status,
    f.created_at,
    c.name AS collection_name,
    u.email AS uploaded_by_email,
    u.full_name AS uploaded_by_full_name,
    j.id AS latest_job_id,
    j.status AS latest_job_status,
    j.current_stage AS latest_job_stage,
    j.progress_percent AS latest_job_progress,
    j.processed_chunks AS latest_job_processed_chunks,
    j.total_chunks AS latest_job_total_chunks
FROM files f
LEFT JOIN collections c ON c.id = f.collection_id
JOIN users u ON u.id = f.uploaded_by
LEFT JOIN LATERAL (
    SELECT
        ij.id,
        ij.status,
        ij.current_stage,
        ij.progress_percent,
        ij.processed_chunks,
        ij.total_chunks
    FROM ingestion_jobs ij
    WHERE ij.file_id = f.id
    ORDER BY ij.created_at DESC
    LIMIT 1
) j ON TRUE
ORDER BY f.created_at DESC
LIMIT %s OFFSET %s;
"""

LIST_FILES_FOR_USER = """
SELECT
    f.id,
    f.collection_id,
    f.uploaded_by,
    f.original_name,
    f.content_type,
    f.size_bytes,
    f.source_type,
    f.total_chunks,
    f.indexed_chunks,
    f.ingestion_status,
    f.created_at,
    c.name AS collection_name,
    j.id AS latest_job_id,
    j.status AS latest_job_status,
    j.current_stage AS latest_job_stage,
    j.progress_percent AS latest_job_progress,
    j.processed_chunks AS latest_job_processed_chunks,
    j.total_chunks AS latest_job_total_chunks
FROM files f
LEFT JOIN collections c ON c.id = f.collection_id
LEFT JOIN LATERAL (
    SELECT
        ij.id,
        ij.status,
        ij.current_stage,
        ij.progress_percent,
        ij.processed_chunks,
        ij.total_chunks
    FROM ingestion_jobs ij
    WHERE ij.file_id = f.id
    ORDER BY ij.created_at DESC
    LIMIT 1
) j ON TRUE
WHERE f.uploaded_by = %s
ORDER BY f.created_at DESC
LIMIT %s OFFSET %s;
"""



def create_file(
    *,
    file_id: UUID,
    collection_id: UUID,
    uploaded_by: UUID,
    original_name: str,
    stored_name: str,
    content_type: str,
    size_bytes: int,
    minio_bucket: str,
    minio_object_key: str,
    checksum_sha256: str,
    source_type: str,
    ingestion_status: str,
    last_ingested_job_id: UUID,
    metadata: dict | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        INSERT_FILE,
        (
            str(file_id),
            str(collection_id),
            str(uploaded_by),
            original_name,
            stored_name,
            content_type,
            size_bytes,
            minio_bucket,
            minio_object_key,
            checksum_sha256,
            source_type,
            ingestion_status,
            str(last_ingested_job_id),
            to_jsonb(metadata),
        ),
        conn=conn,
    )



def get_file(file_id: UUID) -> dict | None:
    return fetch_one(GET_FILE, (str(file_id),))



def list_files_for_admin(limit: int, offset: int) -> list[dict]:
    return fetch_all(LIST_FILES_FOR_ADMIN, (limit, offset))



def list_files_for_user(user_id: UUID, limit: int, offset: int) -> list[dict]:
    return fetch_all(LIST_FILES_FOR_USER, (str(user_id), limit, offset))
