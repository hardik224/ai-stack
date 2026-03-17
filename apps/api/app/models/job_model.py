from uuid import UUID

from app.library.db import execute, execute_returning, fetch_all, fetch_one, to_jsonb


INSERT_INGESTION_JOB = """
INSERT INTO ingestion_jobs (
    id,
    file_id,
    collection_id,
    created_by,
    queue_name,
    status,
    current_stage,
    progress_percent,
    stage_metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING
    id,
    file_id,
    collection_id,
    created_by,
    queue_name,
    status,
    current_stage,
    progress_percent,
    stage_metadata,
    created_at;
"""

INSERT_JOB_EVENT = """
INSERT INTO job_events (
    job_id,
    event_type,
    message,
    event_data,
    created_by_user_id
)
VALUES (%s, %s, %s, %s, %s);
"""

UPSERT_PROCESSING_STAGE = """
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
VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
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

UPDATE_INGESTION_JOB = """
UPDATE ingestion_jobs
SET
    status = %s,
    current_stage = %s,
    progress_percent = %s,
    attempts = COALESCE(%s, attempts),
    started_at = COALESCE(%s, started_at),
    completed_at = %s,
    failed_at = %s,
    error_message = %s,
    worker_id = %s,
    worker_heartbeat_at = NOW(),
    stage_metadata = %s,
    updated_at = NOW()
WHERE id = %s
RETURNING
    id,
    file_id,
    collection_id,
    created_by,
    queue_name,
    status,
    current_stage,
    progress_percent,
    attempts,
    started_at,
    completed_at,
    failed_at,
    error_message,
    worker_id,
    worker_heartbeat_at,
    stage_metadata,
    created_at,
    updated_at;
"""

GET_JOB = """
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
    j.started_at,
    j.completed_at,
    j.failed_at,
    j.error_message,
    j.worker_id,
    j.worker_heartbeat_at,
    j.stage_metadata,
    j.created_at,
    j.updated_at,
    f.original_name AS file_name,
    f.content_type,
    f.size_bytes,
    u.email AS created_by_email,
    c.name AS collection_name
FROM ingestion_jobs j
JOIN files f ON f.id = j.file_id
JOIN users u ON u.id = j.created_by
LEFT JOIN collections c ON c.id = j.collection_id
WHERE j.id = %s;
"""

LIST_JOB_EVENTS = """
SELECT
    id,
    job_id,
    event_type,
    message,
    event_data,
    created_by_user_id,
    created_at
FROM job_events
WHERE job_id = %s
ORDER BY created_at ASC;
"""

LIST_JOB_STAGES = """
SELECT
    id,
    job_id,
    stage_name,
    stage_order,
    stage_status,
    progress_percent,
    details,
    started_at,
    completed_at,
    created_at,
    updated_at
FROM processing_stages
WHERE job_id = %s
ORDER BY stage_order ASC, created_at ASC;
"""

GET_BACKGROUND_TASK = """
SELECT
    id,
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
    error_message,
    created_at,
    updated_at
FROM background_tasks
WHERE job_id = %s AND task_type = %s;
"""

LIST_ADMIN_JOBS_BASE = """
SELECT
    j.id,
    j.file_id,
    f.original_name AS file_name,
    j.collection_id,
    c.name AS collection_name,
    j.created_by,
    u.email AS created_by_email,
    j.status,
    j.current_stage,
    j.progress_percent,
    j.worker_id,
    j.worker_heartbeat_at,
    j.created_at,
    j.started_at,
    j.completed_at,
    j.failed_at,
    j.error_message
FROM ingestion_jobs j
JOIN files f ON f.id = j.file_id
JOIN users u ON u.id = j.created_by
LEFT JOIN collections c ON c.id = j.collection_id
"""

LIST_ADMIN_JOBS_ORDER = """
ORDER BY j.created_at DESC
LIMIT %s OFFSET %s;
"""

JOB_SUMMARY = """
SELECT
    COUNT(*) AS total_jobs,
    COUNT(*) FILTER (WHERE status = 'queued') AS queued_jobs,
    COUNT(*) FILTER (WHERE status = 'processing') AS processing_jobs,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed_jobs,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed_jobs,
    COUNT(*) FILTER (WHERE current_stage = 'validating') AS validating_jobs,
    COUNT(*) FILTER (WHERE current_stage = 'chunking_pending') AS chunking_pending_jobs
FROM ingestion_jobs;
"""

LIST_PROCESSES_BASE = """
SELECT
    bt.id,
    bt.job_id,
    bt.task_type,
    bt.status,
    bt.current_stage,
    bt.progress_percent,
    bt.worker_id,
    bt.heartbeat_at,
    bt.metadata,
    bt.started_at,
    bt.completed_at,
    bt.failed_at,
    bt.error_message,
    bt.created_at,
    bt.updated_at,
    j.file_id,
    f.original_name AS file_name,
    u.email AS created_by_email
FROM background_tasks bt
LEFT JOIN ingestion_jobs j ON j.id = bt.job_id
LEFT JOIN files f ON f.id = j.file_id
LEFT JOIN users u ON u.id = j.created_by
"""

LIST_PROCESSES_ORDER = """
ORDER BY bt.created_at DESC
LIMIT %s OFFSET %s;
"""

PROCESS_SUMMARY = """
SELECT
    COUNT(*) AS total_processes,
    COUNT(*) FILTER (WHERE status = 'queued') AS queued_processes,
    COUNT(*) FILTER (WHERE status = 'running') AS running_processes,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed_processes,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed_processes,
    COALESCE(AVG(progress_percent), 0) AS average_progress_percent
FROM background_tasks;
"""


def create_ingestion_job(
    *,
    job_id: UUID,
    file_id: UUID,
    collection_id: UUID,
    created_by: UUID,
    queue_name: str,
    status: str,
    current_stage: str,
    progress_percent: float,
    stage_metadata: dict | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        INSERT_INGESTION_JOB,
        (
            str(job_id),
            str(file_id),
            str(collection_id),
            str(created_by),
            queue_name,
            status,
            current_stage,
            progress_percent,
            to_jsonb(stage_metadata),
        ),
        conn=conn,
    )


def create_job_event(
    *,
    job_id: UUID,
    event_type: str,
    message: str,
    event_data: dict | None,
    created_by_user_id: UUID | None = None,
    conn=None,
) -> None:
    execute(
        INSERT_JOB_EVENT,
        (
            str(job_id),
            event_type,
            message,
            to_jsonb(event_data),
            str(created_by_user_id) if created_by_user_id else None,
        ),
        conn=conn,
    )


def upsert_processing_stage(
    *,
    job_id: UUID,
    stage_name: str,
    stage_order: int,
    stage_status: str,
    progress_percent: float,
    details: dict | None,
    started_at,
    completed_at,
    conn=None,
) -> None:
    execute(
        UPSERT_PROCESSING_STAGE,
        (
            str(job_id),
            stage_name,
            stage_order,
            stage_status,
            progress_percent,
            to_jsonb(details),
            started_at,
            completed_at,
        ),
        conn=conn,
    )


def upsert_background_task(
    *,
    job_id: UUID,
    task_type: str,
    status: str,
    current_stage: str,
    progress_percent: float,
    worker_id: str | None,
    metadata: dict | None,
    started_at,
    completed_at,
    failed_at,
    error_message: str | None,
    conn=None,
) -> None:
    execute(
        UPSERT_BACKGROUND_TASK,
        (
            str(job_id),
            task_type,
            status,
            current_stage,
            progress_percent,
            worker_id,
            to_jsonb(metadata),
            started_at,
            completed_at,
            failed_at,
            error_message,
        ),
        conn=conn,
    )


def update_ingestion_job(
    *,
    job_id: UUID,
    status: str,
    current_stage: str,
    progress_percent: float,
    attempts: int | None,
    started_at,
    completed_at,
    failed_at,
    error_message: str | None,
    worker_id: str | None,
    stage_metadata: dict | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        UPDATE_INGESTION_JOB,
        (
            status,
            current_stage,
            progress_percent,
            attempts,
            started_at,
            completed_at,
            failed_at,
            error_message,
            worker_id,
            to_jsonb(stage_metadata),
            str(job_id),
        ),
        conn=conn,
    )


def get_job(job_id: UUID) -> dict | None:
    return fetch_one(GET_JOB, (str(job_id),))


def list_job_events(job_id: UUID) -> list[dict]:
    return fetch_all(LIST_JOB_EVENTS, (str(job_id),))


def list_job_stages(job_id: UUID) -> list[dict]:
    return fetch_all(LIST_JOB_STAGES, (str(job_id),))


def get_background_task(job_id: UUID, task_type: str = "ingestion") -> dict | None:
    return fetch_one(GET_BACKGROUND_TASK, (str(job_id), task_type))


def list_admin_jobs(limit: int, offset: int, status: str | None = None) -> list[dict]:
    if status:
        query = LIST_ADMIN_JOBS_BASE + " WHERE j.status = %s " + LIST_ADMIN_JOBS_ORDER
        return fetch_all(query, (status, limit, offset))
    query = LIST_ADMIN_JOBS_BASE + LIST_ADMIN_JOBS_ORDER
    return fetch_all(query, (limit, offset))


def get_job_summary() -> dict:
    return fetch_one(JOB_SUMMARY) or {}


def list_processes(limit: int, offset: int, status: str | None = None) -> list[dict]:
    if status:
        query = LIST_PROCESSES_BASE + " WHERE bt.status = %s " + LIST_PROCESSES_ORDER
        return fetch_all(query, (status, limit, offset))
    query = LIST_PROCESSES_BASE + LIST_PROCESSES_ORDER
    return fetch_all(query, (limit, offset))


def get_process_summary() -> dict:
    return fetch_one(PROCESS_SUMMARY) or {}
