from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.controllers import file_controller
from app.middleware.auth import require_roles


router = APIRouter(tags=["files"])


@router.post("/upload")
def upload_file(
    collection_id: UUID | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("admin", "internal_user")),
):
    return file_controller.upload_file(collection_id=collection_id, file=file, current_user=current_user)


@router.get("/files")
def list_files(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    current_user: dict = Depends(require_roles("admin", "internal_user")),
):
    return file_controller.list_files(current_user=current_user, limit=limit, offset=offset)


@router.get("/files/{file_id}")
def get_file(file_id: UUID, current_user: dict = Depends(require_roles("admin", "internal_user"))):
    return file_controller.get_file(file_id=file_id, current_user=current_user)


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, current_user: dict = Depends(require_roles("admin", "internal_user"))):
    return file_controller.get_job(job_id=job_id, current_user=current_user)
