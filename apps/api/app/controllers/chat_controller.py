from uuid import UUID

from app.schemas.chat import ChatRequest
from app.services import chat_service


def stream_chat(payload: ChatRequest, current_identity: dict):
    return chat_service.stream_chat(payload=payload, current_identity=current_identity)


def list_sessions(current_identity: dict, limit: int, offset: int):
    return chat_service.list_sessions(current_identity=current_identity, limit=limit, offset=offset)


def get_session_details(session_id: UUID, current_identity: dict):
    return chat_service.get_session_details(session_id=session_id, current_identity=current_identity)
