from uuid import UUID

from app.services import admin_service


def get_users(limit: int, offset: int):
    return admin_service.get_users(limit=limit, offset=offset)


def get_user(user_id: UUID):
    return admin_service.get_user_details(user_id)


def get_uploads(limit: int, offset: int):
    return admin_service.get_uploads(limit=limit, offset=offset)


def get_upload_summary():
    return admin_service.get_upload_summary()


def get_chats(limit: int, offset: int):
    return admin_service.get_chat_sessions(limit=limit, offset=offset)


def get_chat(session_id: UUID):
    return admin_service.get_chat_details(session_id)


def get_dashboard_summary():
    return admin_service.get_dashboard_summary()


def get_jobs(limit: int, offset: int, status: str | None):
    return admin_service.get_jobs(limit=limit, offset=offset, status=status)


def get_job(job_id: UUID):
    return admin_service.get_job(job_id)


def get_job_summary():
    return admin_service.get_job_summary()


def get_processes(limit: int, offset: int, status: str | None):
    return admin_service.get_processes(limit=limit, offset=offset, status=status)


def get_process_summary():
    return admin_service.get_process_summary()


def get_recent_activity(limit: int):
    return admin_service.get_recent_activity(limit=limit)
