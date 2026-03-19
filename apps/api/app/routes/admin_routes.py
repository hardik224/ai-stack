from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.controllers import admin_controller
from app.middleware.auth import require_roles
from app.schemas.admin import BulkDeleteRequest


router = APIRouter(prefix="/admin", tags=["admin"])
admin_required = Depends(require_roles("admin"))


@router.get("/users", dependencies=[admin_required])
def get_users(limit: int = Query(default=50), offset: int = Query(default=0)):
    return admin_controller.get_users(limit=limit, offset=offset)


@router.post("/users/bulk-delete", dependencies=[admin_required])
def bulk_delete_users(payload: BulkDeleteRequest, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_users(user_ids=payload.ids, current_user=current_user)


@router.delete("/users/{user_id}", dependencies=[admin_required])
def delete_user(user_id: UUID, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_users(user_ids=[user_id], current_user=current_user)


@router.get("/users/{user_id}", dependencies=[admin_required])
def get_user(user_id: UUID):
    return admin_controller.get_user(user_id=user_id)


@router.get("/uploads", dependencies=[admin_required])
def get_uploads(limit: int = Query(default=50), offset: int = Query(default=0)):
    return admin_controller.get_uploads(limit=limit, offset=offset)


@router.post("/files/bulk-delete", dependencies=[admin_required])
def bulk_delete_files(payload: BulkDeleteRequest, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_files(file_ids=payload.ids, current_user=current_user)


@router.delete("/files/{file_id}", dependencies=[admin_required])
def delete_file(file_id: UUID, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_files(file_ids=[file_id], current_user=current_user)


@router.get("/uploads/summary", dependencies=[admin_required])
def get_upload_summary():
    return admin_controller.get_upload_summary()


@router.get("/chats", dependencies=[admin_required])
def get_chats(limit: int = Query(default=50), offset: int = Query(default=0)):
    return admin_controller.get_chats(limit=limit, offset=offset)


@router.post("/chats/bulk-delete", dependencies=[admin_required])
def bulk_delete_chats(payload: BulkDeleteRequest, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_chats(session_ids=payload.ids, current_user=current_user)


@router.delete("/chats/{session_id}", dependencies=[admin_required])
def delete_chat(session_id: UUID, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_chats(session_ids=[session_id], current_user=current_user)


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


@router.post("/jobs/bulk-delete", dependencies=[admin_required])
def bulk_delete_jobs(payload: BulkDeleteRequest, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_jobs(job_ids=payload.ids, current_user=current_user)


@router.delete("/jobs/{job_id}", dependencies=[admin_required])
def delete_job(job_id: UUID, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_jobs(job_ids=[job_id], current_user=current_user)


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


@router.post("/processes/bulk-delete", dependencies=[admin_required])
def bulk_delete_processes(payload: BulkDeleteRequest, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_processes(process_ids=payload.ids, current_user=current_user)


@router.delete("/processes/{process_id}", dependencies=[admin_required])
def delete_process(process_id: UUID, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_processes(process_ids=[process_id], current_user=current_user)


@router.get("/activity/recent", dependencies=[admin_required])
def get_recent_activity(limit: int = Query(default=20), offset: int = Query(default=0)):
    return admin_controller.get_recent_activity(limit=limit, offset=offset)


@router.post("/collections/bulk-delete", dependencies=[admin_required])
def bulk_delete_collections(payload: BulkDeleteRequest, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_collections(collection_ids=payload.ids, current_user=current_user)


@router.delete("/collections/{collection_id}", dependencies=[admin_required])
def delete_collection(collection_id: UUID, current_user: dict = Depends(require_roles("admin"))):
    return admin_controller.delete_collections(collection_ids=[collection_id], current_user=current_user)
