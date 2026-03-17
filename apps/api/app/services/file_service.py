import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from app.config.settings import get_settings
from app.library.db import transaction
from app.library.queue import enqueue_json
from app.library.security import require_condition, sanitize_filename, utcnow, validate_limit_offset
from app.library.storage import upload_bytes
from app.models import collection_model, file_model, job_model
from app.services.activity_service import record_activity


ALLOWED_UPLOAD_EXTENSIONS = {".pdf": "application/pdf", ".csv": "text/csv"}


def upload_file_to_collection(*, collection_id: UUID, upload: UploadFile, current_user: dict) -> dict:
    settings = get_settings()
    collection = collection_model.get_collection(collection_id)
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found.")

    original_name = sanitize_filename(upload.filename or "upload")
    extension = Path(original_name).suffix.lower()
    require_condition(extension in ALLOWED_UPLOAD_EXTENSIONS, "Only PDF and CSV uploads are supported.")

    content = upload.file.read()
    require_condition(bool(content), "Uploaded file is empty.")
    require_condition(
        len(content) <= settings.max_upload_size_bytes,
        f"File exceeds the maximum size of {settings.max_upload_size_bytes} bytes.",
    )

    content_type = upload.content_type or ALLOWED_UPLOAD_EXTENSIONS[extension]
    checksum_sha256 = hashlib.sha256(content).hexdigest()
    file_id = uuid4()
    job_id = uuid4()
    object_key = f"collections/{collection_id}/{utcnow().strftime('%Y/%m/%d')}/{file_id}{extension}"

    upload_bytes(
        bucket_name=settings.minio_documents_bucket,
        object_key=object_key,
        content=content,
        content_type=content_type,
    )

    with transaction() as conn:
        file_record = file_model.create_file(
            file_id=file_id,
            collection_id=collection_id,
            uploaded_by=current_user["id"],
            original_name=original_name,
            stored_name=f"{file_id}{extension}",
            content_type=content_type,
            size_bytes=len(content),
            minio_bucket=settings.minio_documents_bucket,
            minio_object_key=object_key,
            checksum_sha256=checksum_sha256,
            metadata={"extension": extension},
            conn=conn,
        )
        job_record = job_model.create_ingestion_job(
            job_id=job_id,
            file_id=file_id,
            collection_id=collection_id,
            created_by=current_user["id"],
            queue_name=settings.ingestion_queue_name,
            status="queued",
            current_stage="queued",
            progress_percent=0,
            stage_metadata={"queue_name": settings.ingestion_queue_name},
            conn=conn,
        )
        now = utcnow()
        job_model.upsert_processing_stage(
            job_id=job_id,
            stage_name="queued",
            stage_order=1,
            stage_status="completed",
            progress_percent=0,
            details={"note": "Job queued for worker pickup."},
            started_at=now,
            completed_at=now,
            conn=conn,
        )
        job_model.upsert_background_task(
            job_id=job_id,
            task_type="ingestion",
            status="queued",
            current_stage="queued",
            progress_percent=0,
            worker_id=None,
            metadata={"queue_name": settings.ingestion_queue_name},
            started_at=None,
            completed_at=None,
            failed_at=None,
            error_message=None,
            conn=conn,
        )
        job_model.create_job_event(
            job_id=job_id,
            event_type="job.created",
            message="Ingestion job created and queued.",
            event_data={"file_id": str(file_id), "collection_id": str(collection_id)},
            created_by_user_id=current_user["id"],
            conn=conn,
        )
        record_activity(
            actor_user_id=current_user["id"],
            activity_type="file.uploaded",
            target_type="file",
            target_id=file_id,
            description=f"Uploaded file '{original_name}'.",
            visibility="foreground",
            metadata={"collection_id": str(collection_id), "job_id": str(job_id)},
            conn=conn,
        )

    try:
        enqueue_json(
            settings.ingestion_queue_name,
            {
                "job_id": str(job_id),
                "file_id": str(file_id),
                "collection_id": str(collection_id),
                "uploaded_by": str(current_user["id"]),
            },
        )
    except Exception as exc:
        with transaction() as conn:
            failed_at = utcnow()
            job_model.update_ingestion_job(
                job_id=job_id,
                status="failed",
                current_stage="failed",
                progress_percent=0,
                attempts=None,
                started_at=None,
                completed_at=None,
                failed_at=failed_at,
                error_message=str(exc),
                worker_id=None,
                stage_metadata={"queue_error": str(exc)},
                conn=conn,
            )
            job_model.upsert_background_task(
                job_id=job_id,
                task_type="ingestion",
                status="failed",
                current_stage="failed",
                progress_percent=0,
                worker_id=None,
                metadata={"queue_error": str(exc)},
                started_at=None,
                completed_at=None,
                failed_at=failed_at,
                error_message=str(exc),
                conn=conn,
            )
            job_model.create_job_event(
                job_id=job_id,
                event_type="job.queue_failed",
                message="Failed to push job into Redis queue.",
                event_data={"error": str(exc)},
                created_by_user_id=current_user["id"],
                conn=conn,
            )
            record_activity(
                actor_user_id=current_user["id"],
                activity_type="job.queue_failed",
                target_type="job",
                target_id=job_id,
                description="Job queue push failed.",
                visibility="background",
                metadata={"error": str(exc)},
                conn=conn,
            )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Job queue is unavailable.") from exc

    return {
        "file": file_record,
        "job": job_record,
        "message": "File uploaded and job queued successfully.",
    }


def list_files(*, current_user: dict, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    if current_user["role"] == "admin":
        items = file_model.list_files_for_admin(limit=limit, offset=offset)
    else:
        items = file_model.list_files_for_user(user_id=current_user["id"], limit=limit, offset=offset)
    return {"items": items, "limit": limit, "offset": offset}


def get_file(*, file_id: UUID, current_user: dict) -> dict:
    file_record = file_model.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    if current_user["role"] != "admin" and str(file_record["uploaded_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this file.")
    return file_record


def get_job(*, job_id: UUID, current_user: dict) -> dict:
    job = job_model.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if current_user["role"] != "admin" and str(job["created_by"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this job.")
    return {
        "job": job,
        "events": job_model.list_job_events(job_id),
        "stages": job_model.list_job_stages(job_id),
        "background_task": job_model.get_background_task(job_id),
    }
