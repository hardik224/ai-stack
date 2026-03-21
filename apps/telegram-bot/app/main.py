from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass

import httpx
from telegram import Chat, Update
from telegram.error import RetryAfter
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


def _parse_csv_ints(value: str) -> set[int]:
    items = set()
    for raw in (value or '').split(','):
        text = raw.strip()
        if not text:
            continue
        items.add(int(text))
    return items


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_api_base_url: str
    telegram_api_key: str
    telegram_allowed_chat_ids: set[int]
    telegram_history_limit: int
    telegram_max_history_chars: int
    telegram_polling_timeout: int


def get_settings() -> Settings:
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    api_base_url = os.getenv('TELEGRAM_API_BASE_URL', 'http://api:2000').strip().rstrip('/')
    api_key = os.getenv('TELEGRAM_API_KEY', '').strip()

    if not token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN is required.')
    if not api_key:
        raise RuntimeError('TELEGRAM_API_KEY is required.')

    return Settings(
        telegram_bot_token=token,
        telegram_api_base_url=api_base_url,
        telegram_api_key=api_key,
        telegram_allowed_chat_ids=_parse_csv_ints(os.getenv('TELEGRAM_ALLOWED_CHAT_IDS', '')),
        telegram_history_limit=int(os.getenv('TELEGRAM_HISTORY_LIMIT', '200')),
        telegram_max_history_chars=int(os.getenv('TELEGRAM_MAX_HISTORY_CHARS', '18000')),
        telegram_polling_timeout=int(os.getenv('TELEGRAM_POLLING_TIMEOUT', '30')),
    )


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.telegram_api_base_url,
            headers={'x-api-key': settings.telegram_api_key},
            timeout=httpx.Timeout(60.0),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def ingest_message(self, payload: dict) -> dict:
        response = await self.client.post('/telegram/messages/ingest', json=payload)
        response.raise_for_status()
        return response.json()

    async def respond(self, chat_id: int, payload: dict) -> dict:
        response = await self.client.post(f'/telegram/chats/{chat_id}/respond', json=payload)
        response.raise_for_status()
        return response.json()


async def _prime_bot_identity(application: Application) -> None:
    me = await application.bot.get_me()
    application.bot_data['bot_username'] = me.username or ''
    application.bot_data['bot_id'] = me.id
    print(f"Telegram bot started as @{application.bot_data['bot_username'] or 'unknown'}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not await _is_chat_allowed(update, context):
        return

    await message.reply_text(
        'AI Stack bot is ready.\n'
        'In private chat, just send a message.\n'
        'In groups, mention me, reply to one of my messages, or use /summary, /analyze, or /ask.\n'
        'You can also ask time-scoped prompts like "summarize today" or "analyze last 2 hours".'
    )


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_command_request(update, context, mode='summary')


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_command_request(update, context, mode='analysis')


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_command_request(update, context, mode='assistant')


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or not message.text:
        return
    if not await _is_chat_allowed(update, context):
        return

    await _ingest_effective_message(update, context, message_type='text')

    if chat.type == Chat.PRIVATE:
        await _respond_from_message(update, context, question=message.text.strip(), mode='assistant')
        return

    if await _should_reply_in_shared_chat(update, context):
        question = _clean_group_prompt(message.text, context.application.bot_data.get('bot_username', ''))
        await _respond_from_message(update, context, question=question or message.text.strip(), mode='assistant')


async def _handle_command_request(update: Update, context: ContextTypes.DEFAULT_TYPE, *, mode: str) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return
    if not await _is_chat_allowed(update, context):
        return

    await _ingest_effective_message(update, context, message_type='command')

    args_text = ' '.join(context.args).strip()
    if mode == 'summary':
        question = args_text or 'Summarize the recent conversation in this chat.'
    elif mode == 'analysis':
        question = args_text or 'Analyze the recent conversation in this chat.'
    else:
        question = args_text or 'Help with the latest discussion in this chat.'

    await _respond_from_message(update, context, question=question, mode=mode)


async def _respond_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE, *, question: str, mode: str) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    api_client: ApiClient = context.application.bot_data['api_client']
    settings: Settings = context.application.bot_data['settings']
    try:
        response = await api_client.respond(
            chat.id,
            {
                'question': question,
                'mode': mode,
                'history_limit': settings.telegram_history_limit,
                'max_history_chars': settings.telegram_max_history_chars,
            },
        )
    except httpx.HTTPStatusError as exc:
        detail = _extract_api_error(exc.response)
        await _safe_reply_text(message, f'Bot backend error: {detail}', context=context, is_error=True)
        return
    except Exception:
        await _safe_reply_text(message, 'Bot backend is not reachable right now.', context=context, is_error=True)
        return

    answer = (response.get('answer') or '').strip()
    if not answer:
        await _safe_reply_text(message, 'I could not generate a reply for that yet.', context=context, is_error=True)
        return

    for chunk in _chunk_text(answer, chunk_size=3500):
        sent = await _safe_reply_text(message, chunk, context=context)
        if sent is None:
            return
        await _ingest_sent_message(update, context, sent)


async def _ingest_effective_message(update: Update, context: ContextTypes.DEFAULT_TYPE, *, message_type: str) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or not message.text:
        return

    from_user = message.from_user
    payload = {
        'chat_id': chat.id,
        'chat_type': _normalize_chat_type(chat.type),
        'title': chat.title,
        'username': chat.username,
        'telegram_message_id': message.message_id,
        'telegram_user_id': from_user.id if from_user else None,
        'sender_name': _resolve_sender_name(from_user),
        'sender_username': from_user.username if from_user else None,
        'text': message.text,
        'message_type': message_type,
        'reply_to_message_id': message.reply_to_message.message_id if message.reply_to_message else None,
        'is_bot': bool(from_user.is_bot) if from_user else False,
        'metadata': {},
    }

    api_client: ApiClient = context.application.bot_data['api_client']
    try:
        await api_client.ingest_message(payload)
    except Exception as exc:
        print(f'Failed to ingest Telegram message {message.message_id}: {exc}')


async def _ingest_sent_message(update: Update, context: ContextTypes.DEFAULT_TYPE, sent_message) -> None:
    chat = update.effective_chat
    if chat is None or not sent_message.text:
        return

    bot_username = context.application.bot_data.get('bot_username')
    payload = {
        'chat_id': chat.id,
        'chat_type': _normalize_chat_type(chat.type),
        'title': chat.title,
        'username': chat.username,
        'telegram_message_id': sent_message.message_id,
        'telegram_user_id': sent_message.from_user.id if sent_message.from_user else None,
        'sender_name': bot_username or 'AI Stack Bot',
        'sender_username': bot_username,
        'text': sent_message.text,
        'message_type': 'text',
        'reply_to_message_id': update.effective_message.message_id if update.effective_message else None,
        'is_bot': True,
        'metadata': {},
    }

    api_client: ApiClient = context.application.bot_data['api_client']
    try:
        await api_client.ingest_message(payload)
    except Exception as exc:
        print(f'Failed to ingest bot reply {sent_message.message_id}: {exc}')


async def _should_reply_in_shared_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.effective_message
    if message is None or not message.text:
        return False

    bot_username = context.application.bot_data.get('bot_username')
    if bot_username and f'@{bot_username.lower()}' in message.text.lower():
        return True

    reply_to = message.reply_to_message
    bot_id = context.application.bot_data.get('bot_id')
    if reply_to and reply_to.from_user and bot_id and reply_to.from_user.id == bot_id:
        return True

    return False


async def _is_chat_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False

    settings: Settings = context.application.bot_data['settings']
    allowed = settings.telegram_allowed_chat_ids
    return not allowed or chat.id in allowed


def _normalize_chat_type(chat_type: str) -> str:
    if chat_type in {'private', 'group', 'supergroup', 'channel'}:
        return chat_type
    return 'group'


def _resolve_sender_name(from_user) -> str | None:
    if from_user is None:
        return None
    full_name = ' '.join(part for part in [from_user.first_name, from_user.last_name] if part).strip()
    return full_name or from_user.username


def _clean_group_prompt(text: str, bot_username: str) -> str:
    cleaned = text.strip()
    if bot_username:
        cleaned = re.sub(rf'@{re.escape(bot_username)}\b', '', cleaned, flags=re.IGNORECASE)
    return ' '.join(cleaned.split())


def _chunk_text(text: str, *, chunk_size: int) -> list[str]:
    return [text[start:start + chunk_size] for start in range(0, len(text), chunk_size)] or ['']


def _extract_api_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text or f'HTTP {response.status_code}'
    detail = payload.get('detail')
    return detail if isinstance(detail, str) else response.text or f'HTTP {response.status_code}'


async def _safe_reply_text(message, text: str, *, context: ContextTypes.DEFAULT_TYPE, is_error: bool = False):
    try:
        return await message.reply_text(text, disable_web_page_preview=True)
    except RetryAfter as exc:
        print(f'Skipping Telegram send because of flood control. Retry after {exc.retry_after} seconds.')
        return None
    except Exception as exc:
        prefix = 'error reply' if is_error else 'reply'
        print(f'Failed to send Telegram {prefix}: {exc}')
        return None


async def main() -> None:
    settings = get_settings()
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data['settings'] = settings
    application.bot_data['api_client'] = ApiClient(settings)

    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('summary', summary_command))
    application.add_handler(CommandHandler('analyze', analyze_command))
    application.add_handler(CommandHandler('ask', ask_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    await application.initialize()
    await _prime_bot_identity(application)
    await application.start()
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        timeout=settings.telegram_polling_timeout,
    )

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await application.bot_data['api_client'].close()


if __name__ == '__main__':
    asyncio.run(main())
