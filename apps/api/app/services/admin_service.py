from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from qdrant_client import models as qdrant_models

from app.config.settings import get_settings
from app.library import cache
from app.library.db import transaction
from app.library.qdrant import get_qdrant_client
from app.library.queue import queue_length
from app.library.security import validate_limit_offset
from app.library.storage import delete_object
from app.models import activity_model, admin_model, admin_mutation_model, job_model
from app.services.activity_service import record_activity



def get_users(*, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {'items': admin_model.list_admin_users(limit=limit, offset=offset), 'limit': limit, 'offset': offset}



def get_user_details(user_id):
    user = admin_model.get_admin_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found.')
    return user



def get_uploads(*, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {'items': admin_model.list_uploads(limit=limit, offset=offset), 'limit': limit, 'offset': offset}



def get_upload_summary() -> dict:
    return {'items': admin_model.get_upload_summary()}



def get_chat_sessions(*, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {'items': admin_model.list_chat_sessions(limit=limit, offset=offset), 'limit': limit, 'offset': offset}



def get_chat_details(session_id):
    session = admin_model.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chat session not found.')
    messages = admin_model.list_chat_messages(session_id)
    sources = admin_model.list_chat_message_sources(session_id)
    sources_by_message = defaultdict(list)
    for source in sources:
        sources_by_message[str(source['message_id'])].append(source)
    for message in messages:
        message['sources'] = sources_by_message.get(str(message['id']), [])
    return {'session': session, 'messages': messages, 'sources': sources}



def get_dashboard_summary() -> dict:
    settings = get_settings()
    summary = admin_model.get_dashboard_summary()
    summary['queue_depth'] = queue_length(settings.ingestion_queue_name)
    return summary



def get_jobs(*, limit: int, offset: int, status: str | None) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {
        'items': job_model.list_admin_jobs(limit=limit, offset=offset, status=status),
        'limit': limit,
        'offset': offset,
        'status': status,
    }



def get_job(job_id):
    job = job_model.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found.')
    return {
        'job': job,
        'events': job_model.list_job_events(job_id),
        'stages': job_model.list_job_stages(job_id),
        'background_task': job_model.get_background_task(job_id),
    }



def get_job_summary() -> dict:
    settings = get_settings()
    summary = job_model.get_job_summary()
    summary['queue_depth'] = queue_length(settings.ingestion_queue_name)
    return summary



def get_processes(*, limit: int, offset: int, status: str | None) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {
        'items': job_model.list_processes(limit=limit, offset=offset, status=status),
        'limit': limit,
        'offset': offset,
        'status': status,
    }



def get_process_summary() -> dict:
    settings = get_settings()
    summary = job_model.get_process_summary()
    summary['queue_depth'] = queue_length(settings.ingestion_queue_name)
    return summary



def get_recent_activity(*, limit: int, offset: int = 0) -> dict:
    settings = get_settings()
    safe_limit, safe_offset = validate_limit_offset(limit=limit, offset=offset, default_limit=20, max_limit=settings.max_list_limit)
    return {'items': activity_model.list_recent_activity(limit=safe_limit, offset=safe_offset), 'limit': safe_limit, 'offset': safe_offset}



def _unique_by_id(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    items: list[dict] = []
    for record in records:
        record_id = str(record['id'])
        if record_id in seen:
            continue
        seen.add(record_id)
        items.append(record)
    return items



def _collection_version_key(collection_id: str) -> str:
    return f'{cache.COLLECTION_VERSION_PREFIX}:{collection_id}'



def _bump_retrieval_cache_versions(*, collection_ids: list[str]) -> dict:
    bumped = {'global_version': None, 'collection_versions': {}}
    if collection_ids:
        for collection_id in {value for value in collection_ids if value}:
            bumped['collection_versions'][collection_id] = cache.incr(_collection_version_key(collection_id))
        return bumped
    bumped['global_version'] = cache.incr(cache.GLOBAL_VERSION_KEY)
    return bumped



def _delete_qdrant_points_for_file(file_id: str) -> None:
    settings = get_settings()
    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_chunks_collection,
        points_selector=qdrant_models.FilterSelector(
            filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key='file_id',
                        match=qdrant_models.MatchValue(value=file_id),
                    )
                ]
            )
        ),
    )



def _cleanup_file_artifacts(file_records: list[dict]) -> list[str]:
    warnings: list[str] = []
    for file_record in file_records:
        file_id = str(file_record['id'])
        try:
            _delete_qdrant_points_for_file(file_id)
        except Exception as exc:
            warnings.append(f'qdrant cleanup failed for file {file_id}: {exc}')
        try:
            delete_object(file_record['minio_bucket'], file_record['minio_object_key'])
        except Exception as exc:
            warnings.append(f'storage cleanup failed for file {file_id}: {exc}')
    return warnings



def _delete_files_records(*, file_records: list[dict], actor_user_id: UUID, conn) -> dict:
    unique_records = _unique_by_id(file_records)
    file_ids = [str(record['id']) for record in unique_records]
    collection_ids = [str(record.get('collection_id')) for record in unique_records if record.get('collection_id')]
    admin_mutation_model.delete_files_by_ids(file_ids, conn=conn)
    for record in unique_records:
        record_activity(
            actor_user_id=actor_user_id,
            activity_type='admin.file.deleted',
            target_type='file',
            target_id=record['id'],
            description=f"Admin deleted file '{record['original_name']}'.",
            visibility='foreground',
            metadata={'collection_id': str(record.get('collection_id')) if record.get('collection_id') else None},
            conn=conn,
        )
    return {'count': len(unique_records), 'collection_ids': collection_ids, 'records': unique_records}



def _delete_collections_records(*, collection_records: list[dict], actor_user_id: UUID, conn) -> dict:
    unique_collections = _unique_by_id(collection_records)
    file_records: list[dict] = []
    for collection_record in unique_collections:
        file_records.extend(admin_mutation_model.list_files_for_collection(UUID(str(collection_record['id'])), conn=conn))
    deleted_files = _delete_files_records(file_records=file_records, actor_user_id=actor_user_id, conn=conn) if file_records else {'count': 0, 'collection_ids': [], 'records': []}
    collection_ids = [str(record['id']) for record in unique_collections]
    admin_mutation_model.delete_collections_by_ids(collection_ids, conn=conn)
    for record in unique_collections:
        record_activity(
            actor_user_id=actor_user_id,
            activity_type='admin.collection.deleted',
            target_type='collection',
            target_id=record['id'],
            description=f"Admin deleted collection '{record['name']}'.",
            visibility='foreground',
            metadata={'slug': record.get('slug')},
            conn=conn,
        )
    return {
        'count': len(unique_collections),
        'records': unique_collections,
        'deleted_files': deleted_files,
        'collection_ids': collection_ids + deleted_files.get('collection_ids', []),
        'file_records': deleted_files.get('records', []),
    }



def delete_files(*, file_ids: list[UUID], current_user: dict) -> dict:
    records = admin_mutation_model.get_files_by_ids([str(file_id) for file_id in file_ids])
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No files found to delete.')
    with transaction() as conn:
        deleted = _delete_files_records(file_records=records, actor_user_id=UUID(str(current_user['id'])), conn=conn)
    warnings = _cleanup_file_artifacts(deleted['records'])
    cache_versions = _bump_retrieval_cache_versions(collection_ids=deleted['collection_ids'])
    return {'deleted_count': deleted['count'], 'deleted_ids': [str(record['id']) for record in deleted['records']], 'cache_versions': cache_versions, 'warnings': warnings}



def delete_collections(*, collection_ids: list[UUID], current_user: dict) -> dict:
    records = admin_mutation_model.get_collections_by_ids([str(collection_id) for collection_id in collection_ids])
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No collections found to delete.')
    with transaction() as conn:
        deleted = _delete_collections_records(collection_records=records, actor_user_id=UUID(str(current_user['id'])), conn=conn)
    warnings = _cleanup_file_artifacts(deleted['file_records'])
    cache_versions = _bump_retrieval_cache_versions(collection_ids=deleted['collection_ids'])
    return {'deleted_count': deleted['count'], 'deleted_ids': [str(record['id']) for record in deleted['records']], 'deleted_file_count': deleted['deleted_files']['count'], 'cache_versions': cache_versions, 'warnings': warnings}



def delete_jobs(*, job_ids: list[UUID], current_user: dict) -> dict:
    records = admin_mutation_model.get_jobs_by_ids([str(job_id) for job_id in job_ids])
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No jobs found to delete.')
    with transaction() as conn:
        admin_mutation_model.delete_jobs_by_ids([str(record['id']) for record in records], conn=conn)
        for record in records:
            record_activity(
                actor_user_id=current_user['id'],
                activity_type='admin.job.deleted',
                target_type='job',
                target_id=record['id'],
                description=f"Admin deleted job '{record['id']}'.",
                visibility='foreground',
                metadata={'file_id': str(record.get('file_id')) if record.get('file_id') else None},
                conn=conn,
            )
    return {'deleted_count': len(records), 'deleted_ids': [str(record['id']) for record in records]}



def delete_processes(*, process_ids: list[UUID], current_user: dict) -> dict:
    records = admin_mutation_model.get_processes_by_ids([str(process_id) for process_id in process_ids])
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No processes found to delete.')
    with transaction() as conn:
        admin_mutation_model.delete_processes_by_ids([str(record['id']) for record in records], conn=conn)
        for record in records:
            record_activity(
                actor_user_id=current_user['id'],
                activity_type='admin.process.deleted',
                target_type='process',
                target_id=record['id'],
                description=f"Admin deleted process '{record['id']}'.",
                visibility='foreground',
                metadata={'job_id': str(record.get('job_id')) if record.get('job_id') else None},
                conn=conn,
            )
    return {'deleted_count': len(records), 'deleted_ids': [str(record['id']) for record in records]}



def delete_chat_sessions(*, session_ids: list[UUID], current_user: dict) -> dict:
    records = admin_mutation_model.get_chat_sessions_by_ids([str(session_id) for session_id in session_ids])
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No chat sessions found to delete.')
    with transaction() as conn:
        admin_mutation_model.delete_chat_sessions_by_ids([str(record['id']) for record in records], conn=conn)
        for record in records:
            record_activity(
                actor_user_id=current_user['id'],
                activity_type='admin.chat.deleted',
                target_type='chat_session',
                target_id=record['id'],
                description=f"Admin deleted chat session '{record['title']}'.",
                visibility='foreground',
                metadata={'user_id': str(record.get('user_id')) if record.get('user_id') else None},
                conn=conn,
            )
    return {'deleted_count': len(records), 'deleted_ids': [str(record['id']) for record in records]}



def delete_users(*, user_ids: list[UUID], current_user: dict) -> dict:
    normalized_ids = [str(user_id) for user_id in user_ids]
    if str(current_user['id']) in normalized_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Admins cannot delete their own account from the portal.')

    users = admin_mutation_model.get_users_by_ids(normalized_ids)
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No users found to delete.')

    collection_records: list[dict] = []
    file_records: list[dict] = []
    chat_records: list[dict] = []
    job_records: list[dict] = []
    collection_ids_seen: set[str] = set()
    file_ids_seen: set[str] = set()
    chat_ids_seen: set[str] = set()
    job_ids_seen: set[str] = set()

    for user in users:
        user_id = UUID(str(user['id']))
        for collection_record in admin_mutation_model.list_collections_created_by_user(user_id):
            if str(collection_record['id']) not in collection_ids_seen:
                collection_ids_seen.add(str(collection_record['id']))
                collection_records.append(collection_record)
        for file_record in admin_mutation_model.list_files_for_user(user_id):
            if str(file_record['id']) not in file_ids_seen:
                file_ids_seen.add(str(file_record['id']))
                file_records.append(file_record)
        for chat_record in admin_mutation_model.list_chat_sessions_for_user(user_id):
            if str(chat_record['id']) not in chat_ids_seen:
                chat_ids_seen.add(str(chat_record['id']))
                chat_records.append(chat_record)
        for job_record in admin_mutation_model.list_jobs_for_user(user_id):
            if str(job_record['id']) not in job_ids_seen:
                job_ids_seen.add(str(job_record['id']))
                job_records.append(job_record)

    with transaction() as conn:
        deleted_collections = _delete_collections_records(collection_records=collection_records, actor_user_id=UUID(str(current_user['id'])), conn=conn) if collection_records else {'count': 0, 'records': [], 'deleted_files': {'count': 0}, 'collection_ids': [], 'file_records': []}
        remaining_file_records = [record for record in file_records if str(record['id']) not in {str(item['id']) for item in deleted_collections.get('file_records', [])}]
        deleted_files = _delete_files_records(file_records=remaining_file_records, actor_user_id=UUID(str(current_user['id'])), conn=conn) if remaining_file_records else {'count': 0, 'records': [], 'collection_ids': []}

        # Jobs connected to deleted files will already be removed through cascading deletes.
        existing_job_records = admin_mutation_model.get_jobs_by_ids([str(record['id']) for record in job_records], conn=conn)
        if existing_job_records:
            admin_mutation_model.delete_jobs_by_ids([str(record['id']) for record in existing_job_records], conn=conn)
            for record in existing_job_records:
                record_activity(
                    actor_user_id=current_user['id'],
                    activity_type='admin.job.deleted',
                    target_type='job',
                    target_id=record['id'],
                    description=f"Admin deleted job '{record['id']}' while removing a user.",
                    visibility='foreground',
                    metadata={'file_id': str(record.get('file_id')) if record.get('file_id') else None},
                    conn=conn,
                )

        if chat_records:
            admin_mutation_model.delete_chat_sessions_by_ids([str(record['id']) for record in chat_records], conn=conn)
            for record in chat_records:
                record_activity(
                    actor_user_id=current_user['id'],
                    activity_type='admin.chat.deleted',
                    target_type='chat_session',
                    target_id=record['id'],
                    description=f"Admin deleted chat session '{record['title']}' while removing a user.",
                    visibility='foreground',
                    metadata={'user_id': str(record.get('user_id')) if record.get('user_id') else None},
                    conn=conn,
                )

        admin_mutation_model.delete_users_by_ids(normalized_ids, conn=conn)
        for user in users:
            record_activity(
                actor_user_id=current_user['id'],
                activity_type='admin.user.deleted',
                target_type='user',
                target_id=user['id'],
                description=f"Admin deleted user '{user['email']}'.",
                visibility='foreground',
                metadata={'role': user.get('role')},
                conn=conn,
            )

    cleanup_records = deleted_collections.get('file_records', []) + deleted_files.get('records', [])
    warnings = _cleanup_file_artifacts(cleanup_records)
    cache_versions = _bump_retrieval_cache_versions(collection_ids=deleted_collections.get('collection_ids', []) + deleted_files.get('collection_ids', []))
    return {
        'deleted_count': len(users),
        'deleted_ids': [str(user['id']) for user in users],
        'deleted_collection_count': deleted_collections.get('count', 0),
        'deleted_file_count': deleted_collections.get('deleted_files', {}).get('count', 0) + deleted_files.get('count', 0),
        'deleted_chat_count': len(chat_records),
        'cache_versions': cache_versions,
        'warnings': warnings,
    }
