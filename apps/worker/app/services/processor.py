import json
import time
from datetime import UTC, datetime
from uuid import UUID

from app.config.settings import get_settings
from app.library.db import execute, fetch_one, to_jsonb, transaction
from app.library.queue import pop_job


GET_JOB = """
SELECT
    j.id,
    j.file_id,
    j.collection_id,
    j.created_by,
    j.attempts,
    f.original_name,
    f.content_type,
    f.size_bytes
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

INSERT_EVENT = """
INSERT INTO job_events (job_id, event_type, message, event_data)
VALUES (%s, %s, %s, %s);
"""

INSERT_ACTIVITY = """
INSERT INTO activity_logs (actor_user_id, activity_type, target_type, target_id, description, visibility, metadata)
VALUES (NULL, %s, %s, %s, %s, %s, %s);
"""


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def run_worker_loop() -> None:
    settings = get_settings()
    print(
        json.dumps(
            {
                "service": "worker",
                "status": "started",
                "worker_id": settings.worker_id,
                "queue_name": settings.ingestion_queue_name,
                "timestamp": utcnow().isoformat(),
            }
        ),
        flush=True,
    )

    while True:
        job_payload = pop_job(settings.ingestion_queue_name, settings.block_timeout_seconds)
        if not job_payload:
            continue
        process_job(job_payload)


def process_job(job_payload: dict) -> None:
    settings = get_settings()
    job_id = UUID(job_payload["job_id"])
    job = fetch_one(GET_JOB, (str(job_id),))
    if not job:
        print(json.dumps({"service": "worker", "status": "missing_job", "job_id": str(job_id)}), flush=True)
        return

    started_at = utcnow()
    attempts = int(job["attempts"]) + 1

    try:
        _apply_stage(
            job_id=job_id,
            status="processing",
            stage_name="picked",
            stage_order=2,
            progress_percent=5,
            worker_id=settings.worker_id,
            details={"file_name": job["original_name"]},
            started_at=started_at,
            completed_at=utcnow(),
            event_type="job.picked",
            event_message="Worker picked job from Redis queue.",
            background_status="running",
        )
        _update_job(job_id, "processing", "picked", 5, attempts, started_at, None, None, None, settings.worker_id, {"worker_id": settings.worker_id})

        _simulate_stage(job_id, "validating", 3, 20, "Validating upload metadata.", started_at, attempts, settings.worker_id)
        _simulate_stage(job_id, "processing", 4, 60, "Simulated file processing started.", started_at, attempts, settings.worker_id)
        _simulate_stage(job_id, "chunking_pending", 5, 85, "Chunking and embeddings deferred for future milestone.", started_at, attempts, settings.worker_id)

        completed_at = utcnow()
        _apply_stage(
            job_id=job_id,
            status="completed",
            stage_name="completed",
            stage_order=6,
            progress_percent=100,
            worker_id=settings.worker_id,
            details={"result": "simulated_success"},
            started_at=completed_at,
            completed_at=completed_at,
            event_type="job.completed",
            event_message="Job processing completed.",
            background_status="completed",
        )
        _update_job(
            job_id,
            "completed",
            "completed",
            100,
            attempts,
            started_at,
            completed_at,
            None,
            None,
            settings.worker_id,
            {"result": "simulated_success"},
        )
        print(json.dumps({"service": "worker", "status": "completed", "job_id": str(job_id)}), flush=True)
    except Exception as exc:
        failed_at = utcnow()
        _apply_stage(
            job_id=job_id,
            status="failed",
            stage_name="failed",
            stage_order=99,
            progress_percent=0,
            worker_id=settings.worker_id,
            details={"error": str(exc)},
            started_at=failed_at,
            completed_at=failed_at,
            event_type="job.failed",
            event_message="Job processing failed.",
            background_status="failed",
        )
        _update_job(
            job_id,
            "failed",
            "failed",
            0,
            attempts,
            started_at,
            None,
            failed_at,
            str(exc),
            settings.worker_id,
            {"error": str(exc)},
        )
        print(json.dumps({"service": "worker", "status": "failed", "job_id": str(job_id), "error": str(exc)}), flush=True)


def _simulate_stage(job_id: UUID, stage_name: str, stage_order: int, progress: float, message: str, started_at: datetime, attempts: int, worker_id: str) -> None:
    settings = get_settings()
    time.sleep(settings.simulation_delay_seconds)
    now = utcnow()
    _apply_stage(
        job_id=job_id,
        status="processing",
        stage_name=stage_name,
        stage_order=stage_order,
        progress_percent=progress,
        worker_id=worker_id,
        details={"note": message},
        started_at=now,
        completed_at=now,
        event_type=f"job.{stage_name}",
        event_message=message,
        background_status="running",
    )
    _update_job(job_id, "processing", stage_name, progress, attempts, started_at, None, None, None, worker_id, {"stage": stage_name})


def _apply_stage(
    *,
    job_id: UUID,
    status: str,
    stage_name: str,
    stage_order: int,
    progress_percent: float,
    worker_id: str,
    details: dict,
    started_at: datetime,
    completed_at: datetime | None,
    event_type: str,
    event_message: str,
    background_status: str,
) -> None:
    with transaction() as conn:
        execute(
            UPSERT_STAGE,
            (
                str(job_id),
                stage_name,
                stage_order,
                "completed" if status != "failed" else "failed",
                progress_percent,
                to_jsonb(details),
                started_at,
                completed_at,
            ),
            conn=conn,
        )
        execute(
            UPSERT_BACKGROUND_TASK,
            (
                str(job_id),
                background_status,
                stage_name,
                progress_percent,
                worker_id,
                to_jsonb(details),
                started_at,
                completed_at if background_status == "completed" else None,
                completed_at if background_status == "failed" else None,
                details.get("error"),
            ),
            conn=conn,
        )
        execute(
            INSERT_EVENT,
            (str(job_id), event_type, event_message, to_jsonb(details)),
            conn=conn,
        )
        execute(
            INSERT_ACTIVITY,
            (
                event_type,
                "job",
                str(job_id),
                event_message,
                "background",
                to_jsonb({"stage_name": stage_name, "worker_id": worker_id}),
            ),
            conn=conn,
        )


def _update_job(
    job_id: UUID,
    status: str,
    current_stage: str,
    progress_percent: float,
    attempts: int,
    started_at: datetime,
    completed_at: datetime | None,
    failed_at: datetime | None,
    error_message: str | None,
    worker_id: str,
    metadata: dict,
) -> None:
    execute(
        UPDATE_JOB,
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
            to_jsonb(metadata),
            str(job_id),
        ),
    )
