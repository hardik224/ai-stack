from uuid import UUID

from app.library.db import execute_returning, fetch_all, fetch_one, to_jsonb


UPSERT_TELEGRAM_CHAT = """
INSERT INTO telegram_chats (
    owner_user_id,
    chat_id,
    chat_type,
    title,
    username,
    metadata,
    last_message_at
)
VALUES (%s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (owner_user_id, chat_id)
DO UPDATE SET
    chat_type = EXCLUDED.chat_type,
    title = COALESCE(EXCLUDED.title, telegram_chats.title),
    username = COALESCE(EXCLUDED.username, telegram_chats.username),
    metadata = COALESCE(telegram_chats.metadata, '{}'::jsonb) || EXCLUDED.metadata,
    last_message_at = NOW(),
    updated_at = NOW()
RETURNING id, owner_user_id, chat_id, chat_type, title, username, metadata, last_message_at, created_at, updated_at;
"""

GET_TELEGRAM_CHAT = """
SELECT
    id,
    owner_user_id,
    chat_id,
    chat_type,
    title,
    username,
    metadata,
    last_message_at,
    created_at,
    updated_at
FROM telegram_chats
WHERE owner_user_id = %s AND chat_id = %s;
"""

UPSERT_TELEGRAM_MESSAGE = """
INSERT INTO telegram_messages (
    telegram_chat_id,
    telegram_message_id,
    telegram_user_id,
    sender_name,
    sender_username,
    text_content,
    message_type,
    reply_to_message_id,
    is_bot,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (telegram_chat_id, telegram_message_id)
DO UPDATE SET
    telegram_user_id = EXCLUDED.telegram_user_id,
    sender_name = COALESCE(EXCLUDED.sender_name, telegram_messages.sender_name),
    sender_username = COALESCE(EXCLUDED.sender_username, telegram_messages.sender_username),
    text_content = EXCLUDED.text_content,
    message_type = EXCLUDED.message_type,
    reply_to_message_id = EXCLUDED.reply_to_message_id,
    is_bot = EXCLUDED.is_bot,
    metadata = COALESCE(telegram_messages.metadata, '{}'::jsonb) || EXCLUDED.metadata,
    updated_at = NOW()
RETURNING id, telegram_chat_id, telegram_message_id, telegram_user_id, sender_name, sender_username, text_content, message_type, reply_to_message_id, is_bot, metadata, created_at, updated_at;
"""

LIST_RECENT_TELEGRAM_MESSAGES = """
SELECT
    id,
    telegram_chat_id,
    telegram_message_id,
    telegram_user_id,
    sender_name,
    sender_username,
    text_content,
    message_type,
    reply_to_message_id,
    is_bot,
    metadata,
    created_at,
    updated_at
FROM telegram_messages
WHERE telegram_chat_id = %s
ORDER BY created_at DESC
LIMIT %s;
"""


def upsert_chat(
    *,
    owner_user_id: UUID,
    chat_id: int,
    chat_type: str,
    title: str | None,
    username: str | None,
    metadata: dict | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        UPSERT_TELEGRAM_CHAT,
        (str(owner_user_id), chat_id, chat_type, title, username, to_jsonb(metadata)),
        conn=conn,
    )


def get_chat(*, owner_user_id: UUID, chat_id: int, conn=None) -> dict | None:
    return fetch_one(GET_TELEGRAM_CHAT, (str(owner_user_id), chat_id), conn=conn)


def upsert_message(
    *,
    telegram_chat_id: UUID,
    telegram_message_id: int,
    telegram_user_id: int | None,
    sender_name: str | None,
    sender_username: str | None,
    text_content: str,
    message_type: str,
    reply_to_message_id: int | None,
    is_bot: bool,
    metadata: dict | None,
    conn=None,
) -> dict | None:
    return execute_returning(
        UPSERT_TELEGRAM_MESSAGE,
        (
            str(telegram_chat_id),
            telegram_message_id,
            telegram_user_id,
            sender_name,
            sender_username,
            text_content,
            message_type,
            reply_to_message_id,
            is_bot,
            to_jsonb(metadata),
        ),
        conn=conn,
    )


def list_recent_messages(*, telegram_chat_id: UUID, limit: int, conn=None) -> list[dict]:
    rows = fetch_all(LIST_RECENT_TELEGRAM_MESSAGES, (str(telegram_chat_id), limit), conn=conn)
    rows.reverse()
    return rows
