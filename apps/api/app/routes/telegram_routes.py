from fastapi import APIRouter, Depends

from app.controllers import telegram_controller
from app.middleware.auth import require_chat_access
from app.schemas.telegram import TelegramMessageIngestRequest, TelegramRespondRequest


router = APIRouter(prefix='/telegram', tags=['telegram'])


@router.post('/messages/ingest')
def ingest_message(
    payload: TelegramMessageIngestRequest,
    current_identity: dict = Depends(require_chat_access()),
):
    return telegram_controller.ingest_message(payload=payload, current_identity=current_identity)


@router.post('/chats/{chat_id}/respond')
def respond_to_chat(
    chat_id: int,
    payload: TelegramRespondRequest,
    current_identity: dict = Depends(require_chat_access()),
):
    return telegram_controller.respond_to_chat(chat_id=chat_id, payload=payload, current_identity=current_identity)
