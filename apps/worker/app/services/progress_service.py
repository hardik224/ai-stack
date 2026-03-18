from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.library.db import execute, executemany, fetch_one, to_jsonb, transaction


STAGE_ORDERS = {
    'queued': 1,
    'downloading': 2,
    'parsing': 3,
    'chunking': 4,
    'embedding': 5,
    'indexing': 6,
    'completed': 7,
    'failed': 99,
}

GET_JOB_CONTEXT = """
SELECT
    j.id,
    j.file_id,
    j.collection_id,
    j.created_by,
    j.queue_name,
    j.status,
    j.current_stage,
    j.progress_percent,
    j.attempts,
    j.total_chunks,
    j.processed_chunks,
    j.indexed_chunks,
    j.progress_message,
    f.original_name,
    f.content_type,
    f.size_bytes,
    f.minio_bucket,
    f.minio_object_key,
    f.source_type,
    f.page_count,
    f.row_count
FROM ingestion_jobs j
JOIN files f ON f.id = j.file_id
WHERE j.id = %s;
"""

UPDATE_JOB = """
UPDATE ingestion_jobs
SET
    status = %s,
    current_stage = %s,
    progress_percent = %s,
    attempts = %s,
    started_at = COALESCE(started_at, %s),
    completed_at = %s,
    failed_at = %s,
    error_message = %s,
    worker_id = %s,
    worker_heartbeat_at = NOW(),
    stage_metadata = %s,
    total_chunks = %s,
    processed_chunks = %s,
    indexed_chunks = %s,
    progress_message = %s,
    updated_at = NOW()
WHERE id = %s;
"""

UPSERT_STAGE = """
INSERT INTO processing_stages (
    job_id,
    stage_name,
    stage_order,
    stage_status,
    progress_percent,
    details,
    started_at,
    completed_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (job_id, stage_name)
DO UPDATE SET
    stage_order = EXCLUDED.stage_order,
    stage_status = EXCLUDED.stage_status,
    progress_percent = EXCLUDED.progress_percent,
    details = EXCLUDED.details,
    started_at = COALESCE(processing_stages.started_at, EXCLUDED.started_at),
    completed_at = EXCLUDED.completed_at,
    updated_at = NOW();
"""

UPSERT_BACKGROUND_TASK = """
INSERT INTO background_tasks (
    job_id,
    task_type,
    status,
    current_stage,
    progress_percent,
    worker_id,
    heartbeat_at,
    metadata,
    started_at,
    completed_at,
    failed_at,
    error_message
)
VALUES (%s, 'ingestion', %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
ON CONFLICT (job_id, task_type)
DO UPDATE SET
    status = EXCLUDED.status,
    current_stage = EXCLUDED.current_stage,
    progress_percent = EXCLUDED.progress_percent,
    worker_id = EXCLUDED.worker_id,
    heartbeat_at = NOW(),
    metadata = EXCLUDED.metadata,
    started_at = COALESCE(background_tasks.started_at, EXCLUDED.started_at),
    completed_at = EXCLUDED.completed_at,
    failed_at = EXCLUDED.failed_at,
    error_message = EXCLUDED.error_message,
    updated_at = NOW();
"""

UPDATE_FILE = """
UPDATE files
SET
    source_type = COALESCE(%s, source_type),
    page_count = COALESCE(%s, page_count),
    row_count = COALESCE(%s, row_count),
    total_chunks = COALESCE(%s, total_chunks),
    indexed_chunks = COALESCE(%s, indexed_chunks),
    ingestion_status = %s,
    last_ingested_job_id = %s,
    last_ingested_at = %s,
    error_message = %s,
    metadata = COALESCE(metadata, '{}'::jsonb) || %s,
    updated_at = NOW()
WHERE id = %s;
"""

INSERT_EVENT = """
INSERT INTO job_events (job_id, event_type, message, event_data)
VALUES (%s, %s, %s, %s);
"""

INSERT_ACTIVITY = """
INSERT INTO activity_logs (actor_user_id, activity_type, target_type, target_id, description, visibility, metadata)
VALUES (NULL, %s, %s, %s, %s, %s, %s);
"""

DELETE_FILE_CHUNKS = 'DELETE FROM chunks WHERE file_id = %s;'

INSERT_CHUNK = """
INSERT INTO chunks (
    id,
    file_id,
    job_id,
    collection_id,
    chunk_index,
    content,
    token_count,
    metadata,
    source_type,
    page_number,
    row_number,
    content_hash,
    qdrant_point_id,
    embedding_model,
    indexed_at,
    source_metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

MARK_CHUNKS_INDEXED = """
UPDATE chunks
SET
    embedding_model = %s,
    indexed_at = %s
WHERE id = ANY(%s);
"""


@dataclass(slots=True)
class JobTracker:
    job: dict
    worker_id: str
    started_at: datetime

    def stage(
        self,
        *,
        stage_name: str,
        progress_percent: float,
        message: str,
        stage_status: str,
        details: dict | None = None,
        total_chunks: int | None = None,
        processed_chunks: int | None = None,
        indexed_chunks: int | None = None,
        page_count: int | None = None,
        row_count: int | None = None,
        source_type: str | None = None,
        emit_event: bool = True,
        completed_at: datetime | None = None,
        failed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> None:
        now = utcnow()
        effective_completed_at = completed_at if stage_status in {'completed', 'failed'} else None
        effective_failed_at = failed_at if stage_status == 'failed' else None

        total_chunks = int(self.job.get('total_chunks', 0) or 0) if total_chunks is None else total_chunks
        processed_chunks = int(self.job.get('processed_chunks', 0) or 0) if processed_chunks is None else processed_chunks
        indexed_chunks = int(self.job.get('indexed_chunks', 0) or 0) if indexed_chunks is None else indexed_chunks
        page_count = self.job.get('page_count') if page_count is None else page_count
        row_count = self.job.get('row_count') if row_count is None else row_count
        source_type = self.job.get('source_type') if source_type is None else source_type

        metadata = {
            'file_id': str(self.job['file_id']),
            'collection_id': str(self.job['collection_id']),
            'file_name': self.job['original_name'],
            'source_type': source_type,
            'page_count': page_count,
            'row_count': row_count,
            'total_chunks': total_chunks,
            'processed_chunks': processed_chunks,
            'indexed_chunks': indexed_chunks,
            'progress_message': message,
        }
        if details:
            metadata.update(details)

        if stage_status == 'completed' and stage_name == 'completed':
            job_status = 'completed'
            file_status = 'completed'
            background_status = 'completed'
        elif stage_status == 'failed':
            job_status = 'failed'
            file_status = 'failed'
            background_status = 'failed'
        else:
            job_status = 'processing'
            file_status = stage_name
            background_status = 'running'

        with transaction() as conn:
            execute(
                UPDATE_JOB,
                (
                    job_status,
                    stage_name,
                    progress_percent,
                    int(self.job['attempts']),
                    self.started_at,
                    effective_completed_at if job_status == 'completed' else None,
                    effective_failed_at,
                    error_message,
                    self.worker_id,
                    to_jsonb(metadata),
                    total_chunks,
                    processed_chunks,
                    indexed_chunks,
                    message,
                    str(self.job['id']),
                ),
                conn=conn,
            )
            execute(
                UPSERT_STAGE,
                (
                    str(self.job['id']),
                    stage_name,
                    STAGE_ORDERS[stage_name],
                    stage_status,
                    progress_percent,
                    to_jsonb(metadata),
                    now if stage_status == 'running' else self.started_at,
                    effective_completed_at,
                ),
                conn=conn,
            )
            execute(
                UPSERT_BACKGROUND_TASK,
                (
                    str(self.job['id']),
                    background_status,
                    stage_name,
                    progress_percent,
                    self.worker_id,
                    to_jsonb(metadata),
                    self.started_at,
                    effective_completed_at if background_status == 'completed' else None,
                    effective_failed_at,
                    error_message,
                ),
                conn=conn,
            )
            execute(
                UPDATE_FILE,
                (
                    source_type,
                    page_count,
                    row_count,
                    total_chunks,
                    indexed_chunks,
                    file_status,
                    str(self.job['id']),
                    effective_completed_at if job_status == 'completed' else None,
                    error_message,
                    to_jsonb(
                        {
                            'last_job_stage': stage_name,
                            'last_job_progress': progress_percent,
                            'processed_chunks': processed_chunks,
                            'indexed_chunks': indexed_chunks,
                        }
                    ),
                    str(self.job['file_id']),
                ),
                conn=conn,
            )

            if emit_event:
                event_type = f'job.{stage_name}.{stage_status}'
                execute(
                    INSERT_EVENT,
                    (str(self.job['id']), event_type, message, to_jsonb(metadata)),
                    conn=conn,
                )
                execute(
                    INSERT_ACTIVITY,
                    (
                        event_type,
                        'job',
                        str(self.job['id']),
                        message,
                        'background',
                        to_jsonb({'worker_id': self.worker_id, 'stage_name': stage_name}),
                    ),
                    conn=conn,
                )

        self.job.update(
            {
                'status': job_status,
                'current_stage': stage_name,
                'progress_percent': progress_percent,
                'worker_id': self.worker_id,
                'source_type': source_type,
                'page_count': page_count,
                'row_count': row_count,
                'total_chunks': total_chunks,
                'processed_chunks': processed_chunks,
                'indexed_chunks': indexed_chunks,
                'progress_message': message,
            }
        )



def utcnow() -> datetime:
    return datetime.now(tz=UTC)



def get_job_context(job_id: UUID) -> dict | None:
    return fetch_one(GET_JOB_CONTEXT, (str(job_id),))



def replace_file_chunks(*, job: dict, chunk_rows: list[dict]) -> None:
    with transaction() as conn:
        execute(DELETE_FILE_CHUNKS, (str(job['file_id']),), conn=conn)
        executemany(
            INSERT_CHUNK,
            [
                (
                    str(chunk['id']),
                    str(job['file_id']),
                    str(job['id']),
                    str(job['collection_id']),
                    chunk['chunk_index'],
                    chunk['content'],
                    chunk['token_count'],
                    to_jsonb({'content_hash': chunk['content_hash']}),
                    chunk['source_type'],
                    chunk['page_number'],
                    chunk['row_number'],
                    chunk['content_hash'],
                    str(chunk['qdrant_point_id']),
                    None,
                    None,
                    to_jsonb(chunk['source_metadata']),
                )
                for chunk in chunk_rows
            ],
            conn=conn,
        )



def mark_chunks_indexed(*, chunk_ids: list[str], embedding_model_name: str, indexed_at: datetime) -> None:
    if not chunk_ids:
        return
    execute(MARK_CHUNKS_INDEXED, (embedding_model_name, indexed_at, chunk_ids))
