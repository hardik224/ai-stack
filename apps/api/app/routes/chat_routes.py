from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.controllers import chat_controller
from app.middleware.auth import require_chat_access
from app.schemas.chat import ChatRequest


router = APIRouter(tags=['chat'])


@router.post('/chat')
def stream_chat(
    payload: ChatRequest,
    current_identity: dict = Depends(require_chat_access()),
):
    return chat_controller.stream_chat(payload=payload, current_identity=current_identity)


@router.get('/chat/sessions')
def list_sessions(
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    current_identity: dict = Depends(require_chat_access()),
):
    return chat_controller.list_sessions(current_identity=current_identity, limit=limit, offset=offset)


@router.get('/chat/sessions/{session_id}')
def get_session_details(
    session_id: UUID,
    current_identity: dict = Depends(require_chat_access()),
):
    return chat_controller.get_session_details(session_id=session_id, current_identity=current_identity)
