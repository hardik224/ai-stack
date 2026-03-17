from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.controllers import admin_controller
from app.middleware.auth import require_roles


router = APIRouter(prefix="/admin", tags=["admin"])
admin_required = Depends(require_roles("admin"))


@router.get("/users", dependencies=[admin_required])
def get_users(limit: int = Query(default=50), offset: int = Query(default=0)):
    return admin_controller.get_users(limit=limit, offset=offset)


@router.get("/users/{user_id}", dependencies=[admin_required])
def get_user(user_id: UUID):
    return admin_controller.get_user(user_id=user_id)


@router.get("/uploads", dependencies=[admin_required])
def get_uploads(limit: int = Query(default=50), offset: int = Query(default=0)):
    return admin_controller.get_uploads(limit=limit, offset=offset)


@router.get("/uploads/summary", dependencies=[admin_required])
def get_upload_summary():
    return admin_controller.get_upload_summary()


@router.get("/chats", dependencies=[admin_required])
def get_chats(limit: int = Query(default=50), offset: int = Query(default=0)):
    return admin_controller.get_chats(limit=limit, offset=offset)


@router.get("/chats/{session_id}", dependencies=[admin_required])
def get_chat(session_id: UUID):
    return admin_controller.get_chat(session_id=session_id)


@router.get("/dashboard/summary", dependencies=[admin_required])
def get_dashboard_summary():
    return admin_controller.get_dashboard_summary()


@router.get("/jobs/summary", dependencies=[admin_required])
def get_job_summary():
    return admin_controller.get_job_summary()


@router.get("/jobs", dependencies=[admin_required])
def get_jobs(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    status: str | None = Query(default=None),
):
    return admin_controller.get_jobs(limit=limit, offset=offset, status=status)


@router.get("/jobs/{job_id}", dependencies=[admin_required])
def get_job(job_id: UUID):
    return admin_controller.get_job(job_id=job_id)


@router.get("/processes/summary", dependencies=[admin_required])
def get_process_summary():
    return admin_controller.get_process_summary()


@router.get("/processes", dependencies=[admin_required])
def get_processes(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    status: str | None = Query(default=None),
):
    return admin_controller.get_processes(limit=limit, offset=offset, status=status)


@router.get("/activity/recent", dependencies=[admin_required])
def get_recent_activity(limit: int = Query(default=20)):
    return admin_controller.get_recent_activity(limit=limit)
