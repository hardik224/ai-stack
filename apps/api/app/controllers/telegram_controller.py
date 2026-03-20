from app.services import telegram_service


def ingest_message(payload, current_identity: dict):
    return telegram_service.ingest_message(payload=payload, current_identity=current_identity)


def respond_to_chat(chat_id: int, payload, current_identity: dict):
    return telegram_service.respond_to_chat(chat_id=chat_id, payload=payload, current_identity=current_identity)
