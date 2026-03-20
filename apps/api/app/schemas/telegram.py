from typing import Literal

from pydantic import BaseModel, Field


TelegramChatType = Literal['private', 'group', 'supergroup', 'channel']
TelegramMessageType = Literal['text', 'command', 'summary', 'analysis', 'system']
TelegramRespondMode = Literal['assistant', 'summary', 'analysis']


class TelegramMessageIngestRequest(BaseModel):
    chat_id: int
    chat_type: TelegramChatType
    title: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    telegram_message_id: int
    telegram_user_id: int | None = None
    sender_name: str | None = Field(default=None, max_length=255)
    sender_username: str | None = Field(default=None, max_length=255)
    text: str = Field(min_length=1, max_length=12000)
    message_type: TelegramMessageType = 'text'
    reply_to_message_id: int | None = None
    is_bot: bool = False
    metadata: dict = Field(default_factory=dict)


class TelegramRespondRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    mode: TelegramRespondMode = 'assistant'
    history_limit: int = Field(default=60, ge=1, le=200)
    max_history_chars: int = Field(default=16000, ge=1000, le=50000)
