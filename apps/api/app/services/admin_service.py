from fastapi import HTTPException, status

from app.config.settings import get_settings
from app.library.queue import queue_length
from app.library.security import validate_limit_offset
from app.models import activity_model, admin_model, job_model


def get_users(*, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {"items": admin_model.list_admin_users(limit=limit, offset=offset), "limit": limit, "offset": offset}


def get_user_details(user_id):
    user = admin_model.get_admin_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


def get_uploads(*, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {"items": admin_model.list_uploads(limit=limit, offset=offset), "limit": limit, "offset": offset}


def get_upload_summary() -> dict:
    return {"items": admin_model.get_upload_summary()}


def get_chat_sessions(*, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {"items": admin_model.list_chat_sessions(limit=limit, offset=offset), "limit": limit, "offset": offset}


def get_chat_details(session_id):
    session = admin_model.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")
    messages = admin_model.list_chat_messages(session_id)
    return {"session": session, "messages": messages}


def get_dashboard_summary() -> dict:
    settings = get_settings()
    summary = admin_model.get_dashboard_summary()
    summary["queue_depth"] = queue_length(settings.ingestion_queue_name)
    return summary


def get_jobs(*, limit: int, offset: int, status: str | None) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {
        "items": job_model.list_admin_jobs(limit=limit, offset=offset, status=status),
        "limit": limit,
        "offset": offset,
        "status": status,
    }


def get_job(job_id):
    job = job_model.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return {
        "job": job,
        "events": job_model.list_job_events(job_id),
        "stages": job_model.list_job_stages(job_id),
        "background_task": job_model.get_background_task(job_id),
    }


def get_job_summary() -> dict:
    settings = get_settings()
    summary = job_model.get_job_summary()
    summary["queue_depth"] = queue_length(settings.ingestion_queue_name)
    return summary


def get_processes(*, limit: int, offset: int, status: str | None) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    return {
        "items": job_model.list_processes(limit=limit, offset=offset, status=status),
        "limit": limit,
        "offset": offset,
        "status": status,
    }


def get_process_summary() -> dict:
    settings = get_settings()
    summary = job_model.get_process_summary()
    summary["queue_depth"] = queue_length(settings.ingestion_queue_name)
    return summary


def get_recent_activity(*, limit: int) -> dict:
    settings = get_settings()
    safe_limit, _ = validate_limit_offset(limit=limit, offset=0, default_limit=20, max_limit=settings.max_list_limit)
    return {"items": activity_model.list_recent_activity(limit=safe_limit), "limit": safe_limit}
