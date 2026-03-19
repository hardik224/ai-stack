from uuid import UUID

from fastapi import UploadFile

from app.services import file_service


def upload_file(collection_id: UUID | None, file: UploadFile, current_user: dict):
    return file_service.upload_file_to_collection(
        collection_id=collection_id,
        upload=file,
        current_user=current_user,
    )


def list_files(current_user: dict, limit: int, offset: int):
    return file_service.list_files(current_user=current_user, limit=limit, offset=offset)


def get_file(file_id: UUID, current_user: dict):
    return file_service.get_file(file_id=file_id, current_user=current_user)


def get_job(job_id: UUID, current_user: dict):
    return file_service.get_job(job_id=job_id, current_user=current_user)
