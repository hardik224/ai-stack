from uuid import UUID

from app.services import admin_service, llm_config_service



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



def get_recent_activity(limit: int, offset: int = 0):
    return admin_service.get_recent_activity(limit=limit, offset=offset)



def get_llm_configs():
    return llm_config_service.list_llm_configs()



def get_active_llm_config():
    return llm_config_service.get_active_llm_config_snapshot()



def create_llm_config(payload, current_user: dict):
    return llm_config_service.create_llm_config(payload=payload, current_user=current_user)



def update_llm_config(config_id: UUID, payload, current_user: dict):
    return llm_config_service.update_llm_config(config_id=config_id, payload=payload, current_user=current_user)



def activate_llm_config(config_id: UUID, current_user: dict):
    return llm_config_service.activate_llm_config(config_id=config_id, current_user=current_user)



def delete_llm_config(config_id: UUID, current_user: dict):
    return llm_config_service.delete_llm_config(config_id=config_id, current_user=current_user)



def delete_users(user_ids: list[UUID], current_user: dict):
    return admin_service.delete_users(user_ids=user_ids, current_user=current_user)



def delete_files(file_ids: list[UUID], current_user: dict):
    return admin_service.delete_files(file_ids=file_ids, current_user=current_user)



def delete_jobs(job_ids: list[UUID], current_user: dict):
    return admin_service.delete_jobs(job_ids=job_ids, current_user=current_user)



def delete_processes(process_ids: list[UUID], current_user: dict):
    return admin_service.delete_processes(process_ids=process_ids, current_user=current_user)



def delete_chats(session_ids: list[UUID], current_user: dict):
    return admin_service.delete_chat_sessions(session_ids=session_ids, current_user=current_user)



def delete_collections(collection_ids: list[UUID], current_user: dict):
    return admin_service.delete_collections(collection_ids=collection_ids, current_user=current_user)
