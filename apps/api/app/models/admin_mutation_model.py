from uuid import UUID

from app.library.db import execute, fetch_all, fetch_one


GET_USERS_BY_IDS = """
SELECT id, email, full_name, role
FROM users
WHERE id = ANY(%s);
"""

LIST_COLLECTIONS_CREATED_BY_USER = """
SELECT id, name, slug, created_by
FROM collections
WHERE created_by = %s;
"""

GET_COLLECTIONS_BY_IDS = """
SELECT id, name, slug, created_by
FROM collections
WHERE id = ANY(%s);
"""

LIST_FILES_FOR_COLLECTION = """
SELECT id, collection_id, uploaded_by, original_name, minio_bucket, minio_object_key
FROM files
WHERE collection_id = %s;
"""

LIST_FILES_FOR_USER = """
SELECT id, collection_id, uploaded_by, original_name, minio_bucket, minio_object_key
FROM files
WHERE uploaded_by = %s;
"""

GET_FILES_BY_IDS = """
SELECT id, collection_id, uploaded_by, original_name, minio_bucket, minio_object_key
FROM files
WHERE id = ANY(%s);
"""

GET_JOBS_BY_IDS = """
SELECT id, file_id, collection_id, created_by, status, current_stage
FROM ingestion_jobs
WHERE id = ANY(%s);
"""

LIST_JOBS_FOR_USER = """
SELECT id, file_id, collection_id, created_by, status, current_stage
FROM ingestion_jobs
WHERE created_by = %s;
"""

GET_PROCESSES_BY_IDS = """
SELECT id, job_id, task_type, status, current_stage
FROM background_tasks
WHERE id = ANY(%s);
"""

LIST_CHAT_SESSIONS_FOR_USER = """
SELECT id, user_id, title
FROM chat_sessions
WHERE user_id = %s;
"""

GET_CHAT_SESSIONS_BY_IDS = """
SELECT id, user_id, title
FROM chat_sessions
WHERE id = ANY(%s);
"""

DELETE_USERS_BY_IDS = "DELETE FROM users WHERE id = ANY(%s);"
DELETE_COLLECTIONS_BY_IDS = "DELETE FROM collections WHERE id = ANY(%s);"
DELETE_FILES_BY_IDS = "DELETE FROM files WHERE id = ANY(%s);"
DELETE_JOBS_BY_IDS = "DELETE FROM ingestion_jobs WHERE id = ANY(%s);"
DELETE_PROCESSES_BY_IDS = "DELETE FROM background_tasks WHERE id = ANY(%s);"
DELETE_CHAT_SESSIONS_BY_IDS = "DELETE FROM chat_sessions WHERE id = ANY(%s);"


def get_users_by_ids(user_ids: list[str], conn=None) -> list[dict]:
    if not user_ids:
        return []
    return fetch_all(GET_USERS_BY_IDS, (user_ids,), conn=conn)



def list_collections_created_by_user(user_id: UUID, conn=None) -> list[dict]:
    return fetch_all(LIST_COLLECTIONS_CREATED_BY_USER, (str(user_id),), conn=conn)



def get_collections_by_ids(collection_ids: list[str], conn=None) -> list[dict]:
    if not collection_ids:
        return []
    return fetch_all(GET_COLLECTIONS_BY_IDS, (collection_ids,), conn=conn)



def list_files_for_collection(collection_id: UUID, conn=None) -> list[dict]:
    return fetch_all(LIST_FILES_FOR_COLLECTION, (str(collection_id),), conn=conn)



def list_files_for_user(user_id: UUID, conn=None) -> list[dict]:
    return fetch_all(LIST_FILES_FOR_USER, (str(user_id),), conn=conn)



def get_files_by_ids(file_ids: list[str], conn=None) -> list[dict]:
    if not file_ids:
        return []
    return fetch_all(GET_FILES_BY_IDS, (file_ids,), conn=conn)



def get_jobs_by_ids(job_ids: list[str], conn=None) -> list[dict]:
    if not job_ids:
        return []
    return fetch_all(GET_JOBS_BY_IDS, (job_ids,), conn=conn)



def list_jobs_for_user(user_id: UUID, conn=None) -> list[dict]:
    return fetch_all(LIST_JOBS_FOR_USER, (str(user_id),), conn=conn)



def get_processes_by_ids(process_ids: list[str], conn=None) -> list[dict]:
    if not process_ids:
        return []
    return fetch_all(GET_PROCESSES_BY_IDS, (process_ids,), conn=conn)



def list_chat_sessions_for_user(user_id: UUID, conn=None) -> list[dict]:
    return fetch_all(LIST_CHAT_SESSIONS_FOR_USER, (str(user_id),), conn=conn)



def get_chat_sessions_by_ids(session_ids: list[str], conn=None) -> list[dict]:
    if not session_ids:
        return []
    return fetch_all(GET_CHAT_SESSIONS_BY_IDS, (session_ids,), conn=conn)



def delete_users_by_ids(user_ids: list[str], conn=None) -> None:
    if user_ids:
        execute(DELETE_USERS_BY_IDS, (user_ids,), conn=conn)



def delete_collections_by_ids(collection_ids: list[str], conn=None) -> None:
    if collection_ids:
        execute(DELETE_COLLECTIONS_BY_IDS, (collection_ids,), conn=conn)



def delete_files_by_ids(file_ids: list[str], conn=None) -> None:
    if file_ids:
        execute(DELETE_FILES_BY_IDS, (file_ids,), conn=conn)



def delete_jobs_by_ids(job_ids: list[str], conn=None) -> None:
    if job_ids:
        execute(DELETE_JOBS_BY_IDS, (job_ids,), conn=conn)



def delete_processes_by_ids(process_ids: list[str], conn=None) -> None:
    if process_ids:
        execute(DELETE_PROCESSES_BY_IDS, (process_ids,), conn=conn)



def delete_chat_sessions_by_ids(session_ids: list[str], conn=None) -> None:
    if session_ids:
        execute(DELETE_CHAT_SESSIONS_BY_IDS, (session_ids,), conn=conn)
