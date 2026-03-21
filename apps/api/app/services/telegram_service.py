from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.models import telegram_model
from app.library.error_console import record_backend_error
from app.services import retrieval_service
from app.services.llm_service import get_runtime_llm_config, stream_markdown_answer
from app.services.prompt_service import (
    build_answer_style_guidance,
    build_evidence_overview,
    build_language_guidance,
    format_context_block,
)


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

    question = payload.question.strip()
    time_scope = _resolve_time_scope(question=question)
    effective_history_limit = max(payload.history_limit, 240 if time_scope['since'] else payload.history_limit)
    history_rows = telegram_model.list_scoped_messages(
        telegram_chat_id=UUID(str(chat['id'])),
        limit=effective_history_limit,
        since=time_scope['since'],
        until=time_scope['until'],
    )
    transcript, transcript_count, available_message_count = _build_transcript(
        history_rows=history_rows,
        max_chars=payload.max_history_chars,
    )
    if transcript_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No Telegram messages available for this chat yet.')

    retrieval = None
    kb_context_items: list[dict] = []
    if _should_use_knowledge_base(mode=payload.mode, question=question):
        try:
            retrieval = retrieval_service.retrieve_chunks(
                query=question,
                current_identity=current_identity,
                top_k=8 if payload.mode == 'assistant' else 6,
                max_context_chunks=6 if payload.mode == 'assistant' else 5,
                max_context_chars=9000,
                persist_trace=True,
            )
            if retrieval.get('evidence_assessment', {}).get('is_sufficient'):
                kb_context_items = retrieval.get('items', [])
        except Exception as exc:
            record_backend_error(
                source='telegram.knowledge_base_retrieval_failed',
                message='Telegram knowledge-base retrieval failed; continuing with conversation context only.',
                details={'chat_id': chat_id, 'question': question[:500], 'mode': payload.mode},
                exc=exc,
            )
            retrieval = None

    prompt_messages = _build_telegram_prompt(
        question=question,
        mode=payload.mode,
        chat=chat,
        transcript=transcript,
        transcript_count=transcript_count,
        available_message_count=available_message_count,
        time_scope_label=time_scope['label'],
        kb_context_items=kb_context_items,
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
        'history_message_total_available': available_message_count,
        'time_scope': {
            'label': time_scope['label'],
            'since': time_scope['since'].isoformat() if time_scope['since'] else None,
            'until': time_scope['until'].isoformat() if time_scope['until'] else None,
        },
        'knowledge_base': {
            'used': bool(kb_context_items),
            'candidate_count': retrieval.get('candidate_count', 0) if retrieval else 0,
            'selected_count': len(kb_context_items),
            'evidence_assessment': retrieval.get('evidence_assessment', {}) if retrieval else {},
        },
        'llm': {
            'provider': runtime_llm.provider,
            'model': runtime_llm.model,
            'config_name': runtime_llm.name,
        },
    }


def _build_transcript(*, history_rows: list[dict], max_chars: int) -> tuple[str, int, int]:
    lines: list[str] = []
    total_chars = 0
    included = 0
    formatted_lines = [line for line in (_format_transcript_line(row) for row in history_rows) if line]
    available = len(formatted_lines)

    for line in reversed(formatted_lines):
        projected = total_chars + len(line) + (1 if lines else 0)
        if lines and projected > max_chars:
            break
        lines.append(line)
        total_chars = projected
        included += 1

    lines.reverse()
    return ('\n'.join(lines), included, available)


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


def _build_telegram_prompt(
    *,
    question: str,
    mode: str,
    chat: dict,
    transcript: str,
    transcript_count: int,
    available_message_count: int,
    time_scope_label: str,
    kb_context_items: list[dict],
) -> list[dict[str, str]]:
    system_message = (
        'You are AI Stack Telegram Assistant. '
        'You help in direct messages, groups, and supergroups using two possible sources of context: '
        'the recent Telegram conversation transcript and the AI Stack knowledge base. '
        'Use the transcript for conversation-aware summaries, analysis, and follow-up questions. '
        'Use the knowledge base only for facts grounded in uploaded data. '
        'Do not claim to have seen messages that are not in the transcript. '
        'Do not invent knowledge-base facts when evidence is missing. '
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
    kb_overview = build_evidence_overview(kb_context_items)
    kb_block = format_context_block(kb_context_items) if kb_context_items else '- No grounded knowledge-base evidence retrieved.'
    style_guidance = build_answer_style_guidance(question=question, mode='analysis' if mode in {'summary', 'analysis'} else 'knowledge_qa')
    language_guidance = build_language_guidance(question=question)

    user_prompt = (
        f'Mode: {label}\n'
        f'Chat type: {chat_type}\n'
        f'Chat label: {chat_label}\n\n'
        f'Transcript scope: {time_scope_label}\n'
        f'Transcript messages included: {transcript_count} of {available_message_count}\n\n'
        f'Request:\n{question}\n\n'
        'Recent Telegram transcript:\n'
        f'{transcript}\n\n'
        'Knowledge base evidence overview:\n'
        f'{kb_overview}\n\n'
        'Knowledge base evidence:\n'
        f'{kb_block}\n\n'
        f'{style_guidance}\n'
        f'{language_guidance}\n'
        'Instructions:\n'
        f'- {mode_instruction}\n'
        '- Match the user language when practical.\n'
        '- If the request is about summary or analysis, prioritize the transcript and the requested time scope.\n'
        '- If the request asks for facts, processes, or reference knowledge, use the knowledge base when relevant.\n'
        '- Keep conversation observations separate from knowledge-base facts when both are used.\n'
        '- Use inline citations like [S1] only for knowledge-base claims, not for plain chat observations.\n'
        '- If the user asks for a particular time period, focus on that scope instead of the whole conversation.\n'
        '- If the request is a direct question, answer first and keep it concise unless more detail is needed.\n'
        '- Never mention internal APIs, backend services, or implementation details.\n'
    )

    return [
        {'role': 'system', 'content': system_message},
        {'role': 'user', 'content': user_prompt},
    ]


def _should_use_knowledge_base(*, mode: str, question: str) -> bool:
    lowered = question.lower()
    if mode == 'assistant':
        return True
    kb_cues = (
        'policy', 'document', 'docs', 'knowledge base', 'knowledgebase', 'manual', 'sop',
        'reference', 'api', 'product', 'feature', 'pricing', 'rule', 'rules', 'spec',
        'file', 'files', 'uploaded', 'data', 'repo', 'repository', 'codebase'
    )
    return any(cue in lowered for cue in kb_cues)


def _resolve_time_scope(*, question: str) -> dict:
    now = datetime.now(tz=UTC)
    lowered = question.lower()

    if 'today' in lowered:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return {'since': start, 'until': None, 'label': 'today'}

    if 'yesterday' in lowered:
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = start_today - timedelta(days=1)
        end = start_today
        return {'since': start, 'until': end, 'label': 'yesterday'}

    match = re.search(r'last\s+(\d+)\s*(hour|hours|hr|hrs)', lowered)
    if match:
        hours = max(1, int(match.group(1)))
        return {'since': now - timedelta(hours=hours), 'until': None, 'label': f'last {hours} hour(s)'}

    match = re.search(r'last\s+(\d+)\s*(day|days)', lowered)
    if match:
        days = max(1, int(match.group(1)))
        return {'since': now - timedelta(days=days), 'until': None, 'label': f'last {days} day(s)'}

    if 'this week' in lowered:
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return {'since': start, 'until': None, 'label': 'this week'}

    return {'since': None, 'until': None, 'label': 'recent conversation'}
