from __future__ import annotations

import time
from collections import defaultdict
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from app.config.settings import get_settings
from app.library import cache
from app.library.error_console import record_backend_error
from app.library.security import validate_limit_offset
from app.library.sse import format_sse_comment, format_sse_event
from app.models import chat_model
from app.services import citation_service, retrieval_service
from app.services.activity_service import record_activity
from app.services.llm_service import get_runtime_llm_config, stream_markdown_answer
from app.services.prompt_service import build_chat_prompt, build_insufficient_evidence_markdown, suggest_session_title



SMALLTALK_RESPONSES = {
    'hello': 'Hello! How can I help you today?',
    'hi': 'Hi! How can I help you today?',
    'hey': 'Hey! How can I help you today?',
    'thanks': "You're welcome.",
    'thank you': "You're welcome.",
    'bye': 'Bye! Take care.',
}


def _normalize_smalltalk(text: str) -> str:
    return ' '.join((text or '').strip().lower().split())



def _get_smalltalk_response(text: str) -> str | None:
    normalized = _normalize_smalltalk(text)
    if normalized in SMALLTALK_RESPONSES:
        return SMALLTALK_RESPONSES[normalized]
    if normalized in {'how are you', 'how are you?', 'how r u'}:
        return "I'm doing well. How can I help you today?"
    if normalized in {'help', 'what can you do', 'what can you do?'}:
        return 'I can answer questions, explain things clearly, and help with analysis when needed.'
    return None



def stream_chat(*, payload, current_identity: dict) -> StreamingResponse:
    headers = {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
    }
    return StreamingResponse(
        _chat_event_stream(payload=payload, current_identity=current_identity),
        media_type='text/event-stream',
        headers=headers,
    )



def list_sessions(*, current_identity: dict, limit: int, offset: int) -> dict:
    settings = get_settings()
    limit, offset = validate_limit_offset(limit, offset, settings.default_list_limit, settings.max_list_limit)
    items = chat_model.list_chat_sessions_for_user(user_id=UUID(str(current_identity['id'])), limit=limit, offset=offset)
    return {
        'items': items,
        'limit': limit,
        'offset': offset,
    }



def get_session_details(*, session_id: UUID, current_identity: dict) -> dict:
    session = _get_owned_session(session_id=session_id, current_identity=current_identity)
    messages = chat_model.list_messages_for_session(session_id)
    sources = chat_model.list_message_sources_for_session(session_id)
    sources_by_message: dict[str, list[dict]] = defaultdict(list)
    for source in sources:
        sources_by_message[str(source['message_id'])].append(source)

    for message in messages:
        message['sources'] = sources_by_message.get(str(message['id']), [])

    return {
        'session': session,
        'messages': messages,
    }



def _chat_event_stream(*, payload, current_identity: dict):
    settings = get_settings()
    total_start = time.perf_counter()
    session = None
    session_created = False
    session_id: UUID | None = None
    user_message = None
    assistant_message = None
    mode = payload.mode or settings.chat_default_mode
    runtime_llm = get_runtime_llm_config()

    try:
        effective_collection_id = payload.collection_id
        if payload.session_id:
            session = _get_owned_session(session_id=payload.session_id, current_identity=current_identity)
            session_id = UUID(str(session['id']))
            if effective_collection_id is None and session.get('collection_id'):
                effective_collection_id = UUID(str(session['collection_id']))
        else:
            session = chat_model.create_chat_session(
                user_id=UUID(str(current_identity['id'])),
                collection_id=effective_collection_id,
                title='New Chat',
                metadata={
                    'created_via': 'chat_api',
                    'auth_type': current_identity.get('auth_type', 'session'),
                    'default_mode': mode,
                },
            )
            if not session:
                raise RuntimeError('Failed to create chat session.')
            session_created = True
            session_id = UUID(str(session['id']))
            record_activity(
                actor_user_id=UUID(str(current_identity['id'])),
                activity_type='chat.session.created',
                target_type='chat_session',
                target_id=session_id,
                description='Chat session created.',
                visibility='foreground',
                metadata={
                    'collection_id': str(effective_collection_id) if effective_collection_id else None,
                    'mode': mode,
                },
            )
            yield format_sse_event(
                'session.created',
                {
                    'session': {
                        'id': str(session['id']),
                        'title': session['title'],
                        'collection_id': str(session['collection_id']) if session.get('collection_id') else None,
                        'status': session['status'],
                        'mode': mode,
                    }
                },
                session_id=str(session_id),
            )

        yield format_sse_comment('chat.stream.opened')

        user_message = chat_model.create_chat_message(
            session_id=session_id,
            user_id=UUID(str(current_identity['id'])),
            role='user',
            content=payload.message,
            token_count=_estimate_token_count(payload.message),
            metadata={
                'auth_type': current_identity.get('auth_type', 'session'),
                'mode': mode,
            },
            status='completed',
            error_message=None,
        )
        chat_model.touch_session(
            session_id=session_id,
            collection_id=effective_collection_id,
            metadata={
                'last_user_message_id': str(user_message['id']) if user_message else None,
                'last_mode': mode,
            },
        )
        if session_created:
            chat_model.maybe_update_session_title(session_id=session_id, title=suggest_session_title(payload.message))
        record_activity(
            actor_user_id=UUID(str(current_identity['id'])),
            activity_type='chat.message.user.created',
            target_type='chat_message',
            target_id=UUID(str(user_message['id'])) if user_message else None,
            description='User sent a chat message.',
            visibility='foreground',
            metadata={'session_id': str(session_id), 'mode': mode},
        )

        assistant_message = chat_model.create_chat_message(
            session_id=session_id,
            user_id=None,
            role='assistant',
            content='',
            token_count=0,
            metadata={
                'stream': {'state': 'started'},
                'mode': mode,
                'llm': {'provider': runtime_llm.provider, 'model': runtime_llm.model, 'config_name': runtime_llm.name},
            },
            status='streaming',
            error_message=None,
        )
        assistant_message_id = UUID(str(assistant_message['id']))

        smalltalk_response = _get_smalltalk_response(payload.message)
        if smalltalk_response:
            total_ms = round((time.perf_counter() - total_start) * 1000, 2)
            metadata = {
                'mode': mode,
                'answer': {
                    'format': 'markdown',
                    'streamed': True,
                    'mode': 'smalltalk',
                    'provider': 'deterministic',
                    'model': None,
                },
                'retrieval': {
                    'query': payload.message,
                    'normalized_query': payload.message.strip().lower(),
                    'expanded_query': payload.message.strip().lower(),
                    'filters': {
                        'collection_id': str(effective_collection_id) if effective_collection_id else None,
                        'file_id': str(payload.file_id) if payload.file_id else None,
                        'source_type': payload.source_type,
                    },
                    'candidate_count': 0,
                    'selected_count': 0,
                    'dedupe_removed_count': 0,
                    'cache_hit': False,
                    'cache_version_scope': {},
                    'retrieval_signature': None,
                },
                'timings': {'total_ms': total_ms},
                'citations': [],
                'cache': {
                    'retrieval': {'hit': False, 'lookup_ms': 0.0, 'ttl_seconds': None},
                    'prompt': {'hit': False, 'lookup_ms': 0.0, 'ttl_seconds': None},
                    'answer': {'hit': False, 'lookup_ms': 0.0, 'ttl_seconds': None, 'eligible': False},
                },
            }

            yield format_sse_event(
                'retrieval.completed',
                {
                    'mode': mode,
                    'query': payload.message,
                    'normalized_query': payload.message.strip().lower(),
                    'expanded_query': payload.message.strip().lower(),
                    'count': 0,
                    'candidate_count': 0,
                    'dedupe_removed_count': 0,
                    'filters': metadata['retrieval']['filters'],
                    'timings': {'total_ms': 0.0},
                    'citations': [],
                    'evidence_assessment': {'is_sufficient': True, 'reason': 'smalltalk', 'selected_count': 0},
                    'cache': metadata['cache']['retrieval'],
                },
                session_id=str(session_id),
                message_id=str(assistant_message_id),
            )
            yield format_sse_event(
                'generation.started',
                {
                    'mode': mode,
                    'generation_mode': 'smalltalk',
                    'backend': 'deterministic',
                    'model': None,
                    'cache': metadata['cache']['answer'],
                },
                session_id=str(session_id),
                message_id=str(assistant_message_id),
            )
            for delta in _chunk_text(smalltalk_response):
                yield format_sse_event(
                    'content.delta',
                    {'delta': delta},
                    session_id=str(session_id),
                    message_id=str(assistant_message_id),
                )

            chat_model.update_chat_message(
                message_id=assistant_message_id,
                content=smalltalk_response,
                token_count=_estimate_token_count(smalltalk_response),
                metadata=metadata,
                status='completed',
                error_message=None,
            )
            chat_model.touch_session(
                session_id=session_id,
                collection_id=effective_collection_id,
                metadata={
                    'last_assistant_message_id': str(assistant_message_id),
                    'last_total_ms': total_ms,
                    'last_mode': mode,
                },
            )
            record_activity(
                actor_user_id=UUID(str(current_identity['id'])),
                activity_type='chat.message.assistant.completed',
                target_type='chat_message',
                target_id=assistant_message_id,
                description='Assistant completed a conversational reply.',
                visibility='foreground',
                metadata={'session_id': str(session_id), 'generation_mode': 'smalltalk', 'mode': mode, 'total_ms': total_ms},
            )
            yield format_sse_event(
                'citations.completed',
                {'citations': []},
                session_id=str(session_id),
                message_id=str(assistant_message_id),
            )
            yield format_sse_event(
                'message.saved',
                {'message_id': str(assistant_message_id), 'status': 'completed'},
                session_id=str(session_id),
                message_id=str(assistant_message_id),
            )
            yield format_sse_event(
                'generation.completed',
                {
                    'message_id': str(assistant_message_id),
                    'mode': mode,
                    'status': 'completed',
                    'citation_count': 0,
                    'timings': {'total_ms': total_ms},
                    'generation_mode': 'smalltalk',
                    'cache': metadata['cache'],
                },
                session_id=str(session_id),
                message_id=str(assistant_message_id),
            )
            return

        effective_top_k = payload.top_k or (min(settings.search_max_limit, settings.chat_default_top_k + 2) if mode == 'analysis' else None)
        effective_context_chunks = payload.max_context_chunks or (settings.chat_default_max_context_chunks + 2 if mode == 'analysis' else None)
        effective_context_chars = payload.max_context_chars or (min(24000, settings.chat_default_max_context_chars + 3000) if mode == 'analysis' else None)

        retrieval_started = time.perf_counter()
        yield format_sse_event(
            'retrieval.started',
            {
                'mode': mode,
                'query': payload.message,
                'collection_id': str(effective_collection_id) if effective_collection_id else None,
                'file_id': str(payload.file_id) if payload.file_id else None,
                'source_type': payload.source_type,
                'top_k': effective_top_k or settings.chat_default_top_k,
            },
            session_id=str(session_id),
            message_id=str(assistant_message_id),
        )

        retrieval = retrieval_service.retrieve_chunks(
            query=payload.message,
            current_identity=current_identity,
            session_id=session_id,
            collection_id=effective_collection_id,
            file_id=payload.file_id,
            source_type=payload.source_type,
            top_k=effective_top_k,
            score_threshold=payload.score_threshold,
            dedupe=payload.dedupe,
            max_context_chunks=effective_context_chunks,
            max_context_chars=effective_context_chars,
            persist_trace=True,
            assistant_message_id=assistant_message_id,
        )
        retrieval['timings']['retrieval_wall_ms'] = round((time.perf_counter() - retrieval_started) * 1000, 2)

        citations = _serialize_citations(retrieval.get('items', []))
        evidence_assessment = retrieval.get('evidence_assessment', {})
        answer_citations = citations if evidence_assessment.get('is_sufficient', False) else []
        cache_state = {
            'retrieval': retrieval.get('cache', {}),
            'prompt': {'hit': False, 'lookup_ms': 0.0, 'ttl_seconds': None},
            'answer': {'hit': False, 'lookup_ms': 0.0, 'ttl_seconds': None, 'eligible': False},
        }
        yield format_sse_event(
            'retrieval.completed',
            {
                'mode': mode,
                'query': retrieval['query'],
                'normalized_query': retrieval['normalized_query'],
                'expanded_query': retrieval['expanded_query'],
                'count': retrieval['selected_count'],
                'candidate_count': retrieval['candidate_count'],
                'dedupe_removed_count': retrieval['dedupe_removed_count'],
                'filters': retrieval['filters'],
                'timings': retrieval['timings'],
                'citations': citations,
                'evidence_assessment': evidence_assessment,
                'media_suggestions': retrieval.get('media_suggestions', []),
                'cache': retrieval.get('cache', {}),
            },
            session_id=str(session_id),
            message_id=str(assistant_message_id),
        )

        answer_parts: list[str] = []
        prompt_build_ms = 0.0
        generation_ms = 0.0
        generation_mode = 'llm'

        evidence_assessment = retrieval.get('evidence_assessment', {})
        answer_citations = citations if evidence_assessment.get('is_sufficient', False) else []
        if not retrieval.get('items') or not evidence_assessment.get('is_sufficient', False):
            generation_mode = 'insufficient_evidence'
            answer_signature = {
                'mode': mode,
                'provider': 'deterministic',
                'model': None,
                'identity_scope': _build_identity_scope(current_identity),
                'normalized_query': retrieval['normalized_query'],
                'expanded_query': retrieval['expanded_query'],
                'retrieval_signature': retrieval.get('retrieval_signature'),
                'generation_mode': generation_mode,
            }
            version_scope = retrieval.get('cache_version_scope', {})
            if settings.cache_answer_enabled:
                cached_answer, answer_meta = cache.get_cached_answer(signature=answer_signature, version_scope=version_scope)
                cache_state['answer'] = {
                    **answer_meta,
                    'ttl_seconds': cache.get_ttl(answer_meta['key']),
                    'eligible': True,
                }
                if cached_answer:
                    generation_mode = 'answer_cache'
                    answer_citations = cached_answer.get('citations', [])
                    yield format_sse_event(
                        'generation.started',
                        {
                            'mode': mode,
                            'generation_mode': generation_mode,
                            'backend': 'redis_cache',
                            'model': None,
                            'cache': cache_state['answer'],
                        },
                        session_id=str(session_id),
                        message_id=str(assistant_message_id),
                    )
                    generation_start = time.perf_counter()
                    for delta in _chunk_text(cached_answer.get('content', '')):
                        answer_parts.append(delta)
                        yield format_sse_event(
                            'content.delta',
                            {'delta': delta},
                            session_id=str(session_id),
                            message_id=str(assistant_message_id),
                        )
                    generation_ms = round((time.perf_counter() - generation_start) * 1000, 2)
                else:
                    yield format_sse_event(
                        'generation.started',
                        {
                            'mode': mode,
                            'generation_mode': generation_mode,
                            'backend': 'deterministic',
                            'model': None,
                            'cache': cache_state['answer'],
                        },
                        session_id=str(session_id),
                        message_id=str(assistant_message_id),
                    )
                    fallback_answer = build_insufficient_evidence_markdown(question=payload.message, mode=mode)
                    generation_start = time.perf_counter()
                    for delta in _chunk_text(fallback_answer):
                        answer_parts.append(delta)
                        yield format_sse_event(
                            'content.delta',
                            {'delta': delta},
                            session_id=str(session_id),
                            message_id=str(assistant_message_id),
                        )
                    generation_ms = round((time.perf_counter() - generation_start) * 1000, 2)
                    cache.set_cached_answer(
                        signature=answer_signature,
                        version_scope=version_scope,
                        payload={'content': ''.join(answer_parts).strip(), 'citations': answer_citations, 'generation_mode': 'insufficient_evidence'},
                    )
                    cache_state['answer']['ttl_seconds'] = settings.cache_answer_ttl_seconds
            else:
                yield format_sse_event(
                    'generation.started',
                    {
                        'mode': mode,
                        'generation_mode': generation_mode,
                        'backend': 'deterministic',
                        'model': None,
                        'cache': cache_state['answer'],
                    },
                    session_id=str(session_id),
                    message_id=str(assistant_message_id),
                )
                fallback_answer = build_insufficient_evidence_markdown(question=payload.message, mode=mode)
                generation_start = time.perf_counter()
                for delta in _chunk_text(fallback_answer):
                    answer_parts.append(delta)
                    yield format_sse_event(
                        'content.delta',
                        {'delta': delta},
                        session_id=str(session_id),
                        message_id=str(assistant_message_id),
                    )
                generation_ms = round((time.perf_counter() - generation_start) * 1000, 2)
        else:
            history_rows = chat_model.list_recent_messages_for_session(session_id, settings.chat_history_turns * 2 + 6)
            history_messages = []
            blocked_ids = {str(assistant_message_id), str(user_message['id']) if user_message else None}
            for message in reversed(history_rows):
                if str(message['id']) in blocked_ids:
                    continue
                if not message.get('content'):
                    continue
                history_messages.append(message)

            prompt_signature = {
                'mode': mode,
                'question': payload.message,
                'retrieval_signature': retrieval.get('retrieval_signature'),
                'history_hash': cache.build_hash([
                    {'role': message['role'], 'content': message['content'], 'updated_at': str(message.get('updated_at'))}
                    for message in history_messages
                ]),
            }
            prompt_messages = None
            if settings.cache_prompt_enabled:
                prompt_cached, prompt_meta = cache.get_cached_prompt(
                    signature=prompt_signature,
                    version_scope=retrieval.get('cache_version_scope', {}),
                )
                cache_state['prompt'] = {
                    **prompt_meta,
                    'ttl_seconds': cache.get_ttl(prompt_meta['key']),
                }
                prompt_build_ms = prompt_meta['lookup_ms']
                if prompt_cached:
                    prompt_messages = prompt_cached
            if prompt_messages is None:
                prompt_started = time.perf_counter()
                prompt_messages = build_chat_prompt(
                    question=payload.message,
                    context_items=retrieval['items'],
                    history_messages=history_messages,
                    mode=mode,
                )
                prompt_build_ms = round(prompt_build_ms + ((time.perf_counter() - prompt_started) * 1000), 2)
                cache.set_cached_prompt(
                    signature=prompt_signature,
                    version_scope=retrieval.get('cache_version_scope', {}),
                    payload=prompt_messages,
                )
                if settings.cache_prompt_enabled:
                    cache_state['prompt']['ttl_seconds'] = settings.cache_prompt_ttl_seconds

            yield format_sse_event(
                'generation.started',
                {
                    'mode': mode,
                    'generation_mode': generation_mode,
                    'backend': runtime_llm.provider,
                    'model': runtime_llm.model,
                    'cache': cache_state['prompt'],
                },
                session_id=str(session_id),
                message_id=str(assistant_message_id),
            )

            generation_start = time.perf_counter()
            llm_error = None
            try:
                for delta in stream_markdown_answer(prompt_messages, mode=mode, runtime_config=runtime_llm):
                    if not delta:
                        continue
                    answer_parts.append(delta)
                    yield format_sse_event(
                        'content.delta',
                        {'delta': delta},
                        session_id=str(session_id),
                        message_id=str(assistant_message_id),
                    )
            except Exception as exc:
                llm_error = str(exc)
                record_backend_error(
                    source='chat.llm_generation_failed',
                    message='LLM generation failed during chat response streaming.',
                    details={
                        'session_id': str(session_id),
                        'assistant_message_id': str(assistant_message_id),
                        'mode': mode,
                        'provider': runtime_llm.provider,
                        'model': runtime_llm.model,
                        'question': payload.message[:500],
                    },
                    exc=exc,
                )
                generation_mode = 'grounded_fallback'
                answer_citations = []
                fallback_answer = _build_grounded_fallback_markdown(
                    question=payload.message,
                    citations=answer_citations,
                    mode=mode,
                    error_message=llm_error,
                )
                answer_parts = []
                for delta in _chunk_text(fallback_answer):
                    answer_parts.append(delta)
                    yield format_sse_event(
                        'content.delta',
                        {'delta': delta},
                        session_id=str(session_id),
                        message_id=str(assistant_message_id),
                    )
            generation_ms = round((time.perf_counter() - generation_start) * 1000, 2)

        media_cards = retrieval.get('media_suggestions', []) if generation_mode == 'llm' else []
        final_content = ''.join(answer_parts).strip()
        total_ms = round((time.perf_counter() - total_start) * 1000, 2)
        timings = {
            **retrieval.get('timings', {}),
            'prompt_build_ms': prompt_build_ms,
            'generation_ms': generation_ms,
            'total_ms': total_ms,
        }
        metadata = {
            'mode': mode,
            'answer': {
                'format': 'markdown',
                'streamed': True,
                'mode': generation_mode,
                'provider': runtime_llm.provider if generation_mode == 'llm' else 'deterministic',
                'model': runtime_llm.model if generation_mode == 'llm' else None,
            },
            'retrieval': {
                'query': retrieval['query'],
                'normalized_query': retrieval['normalized_query'],
                'expanded_query': retrieval['expanded_query'],
                'filters': retrieval['filters'],
                'candidate_count': retrieval['candidate_count'],
                'selected_count': retrieval['selected_count'],
                'dedupe_removed_count': retrieval['dedupe_removed_count'],
                'cache_hit': retrieval['cache_hit'],
                'cache_version_scope': retrieval.get('cache_version_scope', {}),
                'retrieval_signature': retrieval.get('retrieval_signature'),
            },
            'timings': timings,
            'citations': answer_citations,
            'cache': cache_state,
            'media_cards': media_cards,
        }

        final_status = 'failed' if generation_mode in {'insufficient_evidence', 'grounded_fallback'} else 'completed'
        final_error_message = ("I couldn't find enough information in the uploaded files." if generation_mode == 'insufficient_evidence' else "Something went wrong while generating the answer. Please contact the administrator." if generation_mode == 'grounded_fallback' else None)

        chat_model.update_chat_message(
            message_id=assistant_message_id,
            content=final_content,
            token_count=_estimate_token_count(final_content),
            metadata=metadata,
            status=final_status,
            error_message=final_error_message,
        )
        if answer_citations:
            citation_service.persist_sources(message_id=assistant_message_id, citations=retrieval['items'])

        session_metadata = {
            'last_assistant_message_id': str(assistant_message_id),
            'last_total_ms': total_ms,
            'last_retrieval_selected_count': retrieval['selected_count'],
            'last_mode': mode,
        }
        if final_status == 'failed':
            session_metadata['last_failed_message_id'] = str(assistant_message_id)

        chat_model.touch_session(
            session_id=session_id,
            collection_id=effective_collection_id,
            metadata=session_metadata,
        )
        record_activity(
            actor_user_id=UUID(str(current_identity['id'])),
            activity_type='chat.message.assistant.failed' if final_status == 'failed' else 'chat.message.assistant.completed',
            target_type='chat_message',
            target_id=assistant_message_id,
            description='Assistant could not answer from grounded evidence.' if generation_mode == 'insufficient_evidence' else 'Assistant response failed because the language model backend was unavailable.' if final_status == 'failed' else 'Assistant completed a grounded answer.',
            visibility='foreground',
            metadata={
                'session_id': str(session_id),
                'citation_count': len(answer_citations),
                'generation_mode': generation_mode,
                'llm_provider': runtime_llm.provider,
                'llm_model': runtime_llm.model,
                'llm_config_name': runtime_llm.name,
                'mode': mode,
                'total_ms': total_ms,
                'cache': cache_state,
            },
        )

        yield format_sse_event(
            'citations.completed',
            {'citations': answer_citations, 'media_cards': media_cards},
            session_id=str(session_id),
            message_id=str(assistant_message_id),
        )
        yield format_sse_event(
            'message.saved',
            {'message_id': str(assistant_message_id), 'status': final_status},
            session_id=str(session_id),
            message_id=str(assistant_message_id),
        )
        yield format_sse_event(
            'generation.completed',
            {
                'message_id': str(assistant_message_id),
                'mode': mode,
                'status': final_status,
                'citation_count': len(answer_citations),
                'timings': timings,
                'generation_mode': generation_mode,
                'media_cards': media_cards,
                'cache': cache_state,
            },
            session_id=str(session_id),
            message_id=str(assistant_message_id),
        )
    except HTTPException as exc:
        if assistant_message:
            _mark_assistant_failed(assistant_message['id'], str(exc.detail), mode=mode)
        yield format_sse_event(
            'error',
            {'detail': exc.detail, 'status_code': exc.status_code, 'mode': mode},
            session_id=str(session_id) if session_id else None,
            message_id=str(assistant_message['id']) if assistant_message else None,
        )
    except Exception as exc:
        if assistant_message:
            _mark_assistant_failed(assistant_message['id'], str(exc), mode=mode)
        yield format_sse_event(
            'error',
            {'detail': str(exc), 'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR, 'mode': mode},
            session_id=str(session_id) if session_id else None,
            message_id=str(assistant_message['id']) if assistant_message else None,
        )




def _build_identity_scope(current_identity: dict) -> dict:
    return {
        'auth_type': current_identity.get('auth_type', 'session'),
        'role': current_identity.get('role'),
        'subject_id': str(current_identity.get('id')) if current_identity.get('id') else None,
    }


def _get_owned_session(*, session_id: UUID, current_identity: dict) -> dict:
    session = chat_model.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chat session not found.')
    if str(session['user_id']) != str(current_identity['id']):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Chat session not found.')
    return session



def _serialize_citations(items: list[dict]) -> list[dict]:
    citations = []
    for item in items:
        citations.append(
            {
                'label': item['citation_label'],
                'chunk_id': str(item['chunk_id']),
                'file_id': str(item['file_id']),
                'filename': item['filename'],
                'collection_id': str(item['collection_id']),
                'collection_name': item.get('collection_name'),
                'page_number': item.get('page_number'),
                'row_number': item.get('row_number'),
                'source_type': item.get('source_type'),
                'metadata': item.get('source_metadata') or {},
                'score': item.get('score'),
                'rank': item.get('rank'),
            }
        )
    return citations



def _chunk_text(text: str, chunk_size: int = 120) -> Iterable[str]:
    for start in range(0, len(text), chunk_size):
        yield text[start:start + chunk_size]



def _estimate_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))



def _build_grounded_fallback_markdown(*, question: str, citations: list[dict], mode: str, error_message: str | None = None) -> str:
    return 'Something went wrong while generating the answer. Please contact the administrator.'



def _mark_assistant_failed(message_id: str, error_message: str, *, mode: str) -> None:
    existing = chat_model.update_chat_message(
        message_id=UUID(str(message_id)),
        content='',
        token_count=0,
        metadata={'stream': {'state': 'failed'}, 'mode': mode},
        status='failed',
        error_message=error_message[:4000],
    )
    if existing:
        session_id = UUID(str(existing['session_id']))
        chat_model.touch_session(
            session_id=session_id,
            collection_id=None,
            metadata={'last_failed_message_id': str(message_id), 'last_mode': mode},
        )




