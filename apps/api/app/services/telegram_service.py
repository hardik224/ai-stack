from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from app.models import telegram_model
from app.services.llm_service import get_runtime_llm_config, stream_markdown_answer


TELEGRAM_MODE_LABELS = {
    'assistant': 'Assistant',
    'summary': 'Summary',
    'analysis': 'Analysis',
}


def ingest_message(*, payload, current_identity: dict) -> dict:
    owner_user_id = UUID(str(current_identity['id']))
    chat = telegram_model.upsert_chat(
        owner_user_id=owner_user_id,
        chat_id=payload.chat_id,
        chat_type=payload.chat_type,
        title=payload.title,
        username=payload.username,
        metadata=payload.metadata,
    )
    if not chat:
        raise RuntimeError('Failed to create or update Telegram chat.')

    message = telegram_model.upsert_message(
        telegram_chat_id=UUID(str(chat['id'])),
        telegram_message_id=payload.telegram_message_id,
        telegram_user_id=payload.telegram_user_id,
        sender_name=payload.sender_name,
        sender_username=payload.sender_username,
        text_content=payload.text.strip(),
        message_type=payload.message_type,
        reply_to_message_id=payload.reply_to_message_id,
        is_bot=payload.is_bot,
        metadata=payload.metadata,
    )
    return {
        'chat': chat,
        'message': message,
    }


def respond_to_chat(*, chat_id: int, payload, current_identity: dict) -> dict:
    owner_user_id = UUID(str(current_identity['id']))
    chat = telegram_model.get_chat(owner_user_id=owner_user_id, chat_id=chat_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Telegram chat not found. Ingest a message first.')

    history_rows = telegram_model.list_recent_messages(telegram_chat_id=UUID(str(chat['id'])), limit=payload.history_limit)
    transcript, transcript_count = _build_transcript(history_rows=history_rows, max_chars=payload.max_history_chars)
    if transcript_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No Telegram messages available for this chat yet.')

    prompt_messages = _build_telegram_prompt(
        question=payload.question.strip(),
        mode=payload.mode,
        chat=chat,
        transcript=transcript,
    )

    runtime_llm = get_runtime_llm_config()
    answer_parts: list[str] = []
    llm_mode = 'analysis' if payload.mode in {'summary', 'analysis'} else 'knowledge_qa'
    for delta in stream_markdown_answer(prompt_messages, mode=llm_mode, runtime_config=runtime_llm):
        if delta:
            answer_parts.append(delta)

    answer = ''.join(answer_parts).strip()
    if not answer:
        raise RuntimeError('Telegram response generation returned empty content.')

    return {
        'chat_id': chat_id,
        'mode': payload.mode,
        'answer': answer,
        'history_message_count': transcript_count,
        'llm': {
            'provider': runtime_llm.provider,
            'model': runtime_llm.model,
            'config_name': runtime_llm.name,
        },
    }


def _build_transcript(*, history_rows: list[dict], max_chars: int) -> tuple[str, int]:
    lines: list[str] = []
    total_chars = 0
    included = 0

    for row in reversed(history_rows):
        line = _format_transcript_line(row)
        if not line:
            continue
        projected = total_chars + len(line) + (1 if lines else 0)
        if lines and projected > max_chars:
            break
        lines.append(line)
        total_chars = projected
        included += 1

    lines.reverse()
    return ('\n'.join(lines), included)


def _format_transcript_line(row: dict) -> str:
    text = ' '.join((row.get('text_content') or '').split())
    if not text:
        return ''

    created_at = row.get('created_at')
    timestamp = _format_timestamp(created_at)
    sender = row.get('sender_name') or row.get('sender_username') or ('Bot' if row.get('is_bot') else 'Unknown')
    prefix = 'Bot' if row.get('is_bot') else sender
    return f'[{timestamp}] {prefix}: {text[:1000]}'


def _format_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return 'unknown-time'
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    return str(value)


def _build_telegram_prompt(*, question: str, mode: str, chat: dict, transcript: str) -> list[dict[str, str]]:
    system_message = (
        'You are AI Stack Telegram Assistant. '
        'You help in direct messages, groups, supergroups, and channels using only the recent Telegram conversation transcript provided. '
        'Do not claim to have seen messages that are not in the transcript. '
        'If context is missing, say so plainly. '
        'Keep replies clear, useful, and natural for Telegram. '
        'Use compact markdown when it improves readability, but do not over-format.'
    )

    mode_instruction = {
        'assistant': (
            'Reply as an active participant in the conversation. '
            'Answer the user directly, using the recent chat transcript as context when helpful.'
        ),
        'summary': (
            'Summarize the recent conversation clearly. '
            'Focus on the main topics, decisions, questions, blockers, and next steps when they appear.'
        ),
        'analysis': (
            'Analyze the recent conversation carefully. '
            'Identify patterns, sentiment, repeated issues, open questions, risks, and likely next actions when supported by the transcript.'
        ),
    }[mode]

    chat_label = chat.get('title') or chat.get('username') or str(chat.get('chat_id'))
    chat_type = chat.get('chat_type') or 'unknown'
    label = TELEGRAM_MODE_LABELS.get(mode, 'Assistant')

    user_prompt = (
        f'Mode: {label}\n'
        f'Chat type: {chat_type}\n'
        f'Chat label: {chat_label}\n\n'
        f'Request:\n{question}\n\n'
        'Recent Telegram transcript:\n'
        f'{transcript}\n\n'
        'Instructions:\n'
        f'- {mode_instruction}\n'
        '- Match the user language when practical.\n'
        '- If the request is about summary or analysis, base it on the transcript only.\n'
        '- If the request is a direct question, answer first and keep it concise unless more detail is needed.\n'
        '- Never mention internal APIs, backend services, or implementation details.\n'
    )

    return [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': user_prompt},
    ]
