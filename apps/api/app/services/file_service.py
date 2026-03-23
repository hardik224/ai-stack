import hashlib
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.config.settings import get_settings
from app.library.db import transaction
from app.library.queue import enqueue_json
from app.library.security import require_condition, sanitize_filename, slugify, utcnow, validate_limit_offset
from app.library.storage import download_bytes, upload_bytes
from app.models import collection_model, file_model, job_model
from app.services.activity_service import record_activity


ALLOWED_UPLOAD_TYPES = {
    '.pdf': {'content_type': 'application/pdf', 'source_type': 'pdf'},
    '.csv': {'content_type': 'text/csv', 'source_type': 'csv'},
    '.xlsx': {'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'source_type': 'excel'},
    '.xls': {'content_type': 'application/vnd.ms-excel', 'source_type': 'excel'},
    '.txt': {'content_type': 'text/plain', 'source_type': 'txt'},
    '.json': {'content_type': 'application/json', 'source_type': 'json'},
}


def resolve_upload_collection(*, collection_id: UUID | None, current_user: dict, conn=None) -> tuple[dict, bool]:
    if collection_id:
        collection = collection_model.get_collection(collection_id)
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found.')
        return collection, False

    owner_label = (current_user.get('full_name') or current_user.get('email') or 'User').strip()
    managed_slug = slugify(f"managed-uploads-{current_user['id']}")
    existing = collection_model.get_collection_by_slug(managed_slug)
    collection = collection_model.upsert_collection_by_slug(
        name=f'{owner_label} Uploads',
        slug=managed_slug,
        description='System-managed upload space automatically assigned during file upload.',
        visibility='internal',
        metadata={
            'managed_by_system': True,
            'purpose': 'default_upload_target',
            'owner_user_id': str(current_user['id']),
        },
        created_by=current_user['id'],
        conn=conn,
    )
    return collection, existing is None



def upload_file_to_collection(*, collection_id: UUID | None, upload: UploadFile, current_user: dict) -> dict:
    settings = get_settings()
    collection, collection_created = resolve_upload_collection(collection_id=collection_id, current_user=current_user)

    original_name = sanitize_filename(upload.filename or 'upload')
    extension = Path(original_name).suffix.lower()
    require_condition(extension in ALLOWED_UPLOAD_TYPES, 'Only PDF, CSV, Excel, TXT, and JSON uploads are supported.')

    content = upload.file.read()
    require_condition(bool(content), 'Uploaded file is empty.')
    require_condition(
        len(content) <= settings.max_upload_size_bytes,
        f'File exceeds the maximum size of {settings.max_upload_size_bytes} bytes.',
    )

    if extension == '.json':
        try:
            json.loads(content.decode('utf-8-sig', errors='strict'))
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='JSON uploads must be valid UTF-8 text.') from exc
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Invalid JSON file: {exc.msg} at line {exc.lineno}, column {exc.colno}.') from exc

    upload_type = ALLOWED_UPLOAD_TYPES[extension]
    content_type = upload.content_type or upload_type['content_type']
    checksum_sha256 = hashlib.sha256(content).hexdigest()
    file_id = uuid4()
    job_id = uuid4()
    source_type = upload_type['source_type']
    object_key = f"collections/{collection['id']}/{utcnow().strftime('%Y/%m/%d')}/{file_id}{extension}"

    upload_bytes(
        bucket_name=settings.minio_documents_bucket,
        object_key=object_key,
        content=content,
        content_type=content_type,
    )

    with transaction() as conn:
        file_record = file_model.create_file(
            file_id=file_id,
            collection_id=collection['id'],
            uploaded_by=current_user['id'],
            original_name=original_name,
            stored_name=f'{file_id}{extension}',
            content_type=content_type,
            size_bytes=len(content),
            minio_bucket=settings.minio_documents_bucket,
            minio_object_key=object_key,
            checksum_sha256=checksum_sha256,
            source_type=source_type,
            ingestion_status='queued',
            last_ingested_job_id=job_id,
            metadata={'extension': extension},
            conn=conn,
        )
        job_record = job_model.create_ingestion_job(
            job_id=job_id,
            file_id=file_id,
            collection_id=collection['id'],
            created_by=current_user['id'],
            queue_name=settings.ingestion_queue_name,
            status='queued',
            current_stage='queued',
            progress_percent=0,
            total_chunks=0,
            processed_chunks=0,
            indexed_chunks=0,
            progress_message='Upload stored and queued for processing.',
            stage_metadata={'queue_name': settings.ingestion_queue_name, 'source_type': source_type},
            conn=conn,
        )
        now = utcnow()
        job_model.upsert_processing_stage(
            job_id=job_id,
            stage_name='queued',
            stage_order=1,
            stage_status='completed',
            progress_percent=0,
            details={'note': 'Job queued for worker pickup.'},
            started_at=now,
            completed_at=now,
            conn=conn,
        )
        job_model.upsert_background_task(
            job_id=job_id,
            task_type='ingestion',
            status='queued',
            current_stage='queued',
            progress_percent=0,
            worker_id=None,
            metadata={'queue_name': settings.ingestion_queue_name, 'source_type': source_type},
            started_at=None,
            completed_at=None,
            failed_at=None,
            error_message=None,
            conn=conn,
        )
        job_model.create_job_event(
            job_id=job_id,
            event_type='job.created',
            message='Ingestion job created and queued.',
            event_data={'file_id': str(file_id), 'collection_id': str(collection['id']), 'source_type': source_type},
            created_by_user_id=current_user['id'],
            conn=conn,
        )
        if collection_created:
            record_activity(
                actor_user_id=current_user['id'],
                activity_type='collection.auto_created',
                target_type='collection',
                target_id=collection['id'],
                description=f"System created upload collection '{collection['name']}'.",
                visibility='foreground',
                metadata={'collection_id': str(collection['id']), 'managed_by_system': True},
                conn=conn,
            )
        record_activity(
            actor_user_id=current_user['id'],
            activity_type='file.uploaded',
            target_type='file',
            target_id=file_id,
            description=f"Uploaded file '{original_name}'.",
            visibility='foreground',
            metadata={'collection_id': str(collection['id']), 'job_id': str(job_id), 'source_type': source_type, 'collection_auto_assigned': collection_id is None},
            conn=conn,
        )

    try:
        enqueue_json(
            settings.ingestion_queue_name,
            {
                'job_id': str(job_id),
                'file_id': str(file_id),
                'collection_id': str(collection['id']),
                'uploaded_by': str(current_user['id']),
                'source_type': source_type,
            },
        )
    except Exception as exc:
        with transaction() as conn:
            failed_at = utcnow()
            job_model.update_ingestion_job(
                job_id=job_id,
                status='failed',
                current_stage='failed',
                progress_percent=0,
                attempts=None,
                started_at=None,
                completed_at=None,
                failed_at=failed_at,
                error_message=str(exc),
                worker_id=None,
                stage_metadata={'queue_error': str(exc)},
                total_chunks=0,
                processed_chunks=0,
                indexed_chunks=0,
                progress_message='Failed to queue ingestion job.',
                conn=conn,
            )
            job_model.upsert_background_task(
                job_id=job_id,
                task_type='ingestion',
                status='failed',
                current_stage='failed',
                progress_percent=0,
                worker_id=None,
                metadata={'queue_error': str(exc)},
                started_at=None,
                completed_at=None,
                failed_at=failed_at,
                error_message=str(exc),
                conn=conn,
            )
            job_model.create_job_event(
                job_id=job_id,
                event_type='job.queue_failed',
                message='Failed to push job into Redis queue.',
                event_data={'error': str(exc)},
                created_by_user_id=current_user['id'],
                conn=conn,
            )
            record_activity(
                actor_user_id=current_user['id'],
                activity_type='job.queue_failed',
                target_type='job',
                target_id=job_id,
                description='Job queue push failed.',
                visibility='background',
                metadata={'error': str(exc)},
                conn=conn,
            )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Job queue is unavailable.') from exc

    return {
        'file': file_record,
        'job': job_record,
        'message': 'File uploaded and job queued successfully.',
        'collection': {
            'id': collection['id'],
            'name': collection['name'],
            'auto_assigned': collection_id is None,
            'created_now': collection_created,
        },
    }



def list_files(*, current_user: dict, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    if current_user['role'] == 'admin':
        items = file_model.list_files_for_admin(limit=limit, offset=offset)
    else:
        items = file_model.list_files_for_user(user_id=current_user['id'], limit=limit, offset=offset)
    return {'items': items, 'limit': limit, 'offset': offset}



def get_file(*, file_id: UUID, current_user: dict) -> dict:
    file_record = file_model.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='File not found.')
    if current_user['role'] != 'admin' and str(file_record['uploaded_by']) != str(current_user['id']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not allowed to view this file.')

    latest_job_id = file_record.get('latest_job_id')
    latest_job_details = get_job(job_id=latest_job_id, current_user=current_user) if latest_job_id else None
    file_record['ingestion_summary'] = {
        'status': file_record.get('ingestion_status'),
        'source_type': file_record.get('source_type'),
        'page_count': file_record.get('page_count'),
        'row_count': file_record.get('row_count'),
        'total_chunks': file_record.get('total_chunks'),
        'indexed_chunks': file_record.get('indexed_chunks'),
        'last_ingested_job_id': file_record.get('last_ingested_job_id'),
        'last_ingested_at': file_record.get('last_ingested_at'),
        'error_message': file_record.get('error_message'),
    }
    if latest_job_details:
        file_record['latest_job'] = latest_job_details['job']
        file_record['latest_job_stages'] = latest_job_details['stages']
        file_record['latest_job_background_task'] = latest_job_details['background_task']
    return file_record



def get_job(*, job_id: UUID, current_user: dict) -> dict:
    job = job_model.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found.')
    if current_user['role'] != 'admin' and str(job['created_by']) != str(current_user['id']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not allowed to view this job.')
    return {
        'job': job,
        'events': job_model.list_job_events(job_id),
        'stages': job_model.list_job_stages(job_id),
        'background_task': job_model.get_background_task(job_id),
        'progress': {
            'current_stage': job.get('current_stage'),
            'progress_percent': job.get('progress_percent'),
            'progress_message': job.get('progress_message'),
            'total_chunks': job.get('total_chunks'),
            'processed_chunks': job.get('processed_chunks'),
            'indexed_chunks': job.get('indexed_chunks'),
            'started_at': job.get('started_at'),
            'completed_at': job.get('completed_at'),
            'failed_at': job.get('failed_at'),
            'error_message': job.get('error_message'),
        },
    }



def download_file(*, file_id: UUID, current_user: dict):
    file_record = file_model.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='File not found.')
    if current_user['role'] != 'admin' and str(file_record['uploaded_by']) != str(current_user['id']):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not allowed to download this file.')

    content = download_bytes(file_record['minio_bucket'], file_record['minio_object_key'])
    filename = file_record.get('original_name') or f"{file_record['id']}"
    headers = {'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(
        BytesIO(content),
        media_type=file_record.get('content_type') or 'application/octet-stream',
        headers=headers,
    )
