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
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    f.metadata,
    f.created_at,
    f.updated_at,
    c.name AS collection_name,
    u.email AS uploaded_by_email,
    u.full_name AS uploaded_by_full_name,
    j.id AS latest_job_id,
    j.status AS latest_job_status,
    j.current_stage AS latest_job_stage,
    j.progress_percent AS latest_job_progress
FROM files f
LEFT JOIN collections c ON c.id = f.collection_id
JOIN users u ON u.id = f.uploaded_by
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
    f.created_at,
    c.name AS collection_name,
    u.email AS uploaded_by_email,
    u.full_name AS uploaded_by_full_name,
    j.id AS latest_job_id,
    j.status AS latest_job_status,
    j.current_stage AS latest_job_stage,
    j.progress_percent AS latest_job_progress
FROM files f
LEFT JOIN collections c ON c.id = f.collection_id
JOIN users u ON u.id = f.uploaded_by
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

LIST_FILES_FOR_USER = """
SELECT
    f.id,
    f.collection_id,
    f.uploaded_by,
    f.original_name,
    f.content_type,
    f.size_bytes,
    f.created_at,
    c.name AS collection_name,
    j.id AS latest_job_id,
    j.status AS latest_job_status,
    j.current_stage AS latest_job_stage,
    j.progress_percent AS latest_job_progress
FROM files f
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
