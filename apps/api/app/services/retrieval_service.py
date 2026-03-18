import hashlib
import json
import re
import time
from collections import Counter
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from qdrant_client import models

from app.config.settings import get_settings
from app.library.embeddings import embed_query
from app.library.qdrant import get_qdrant_client
from app.library.queue import cache_get_json, cache_set_json
from app.models import chat_model, collection_model, retrieval_model


WORD_RE = re.compile(r'[a-z0-9]+')
SPACE_RE = re.compile(r'\s+')



def retrieve_chunks(
    *,
    query: str,
    current_identity: dict,
    session_id: UUID | None = None,
    collection_id: UUID | None = None,
    file_id: UUID | None = None,
    source_type: str | None = None,
    top_k: int | None = None,
    score_threshold: float | None = None,
    dedupe: bool = True,
    max_context_chunks: int | None = None,
    max_context_chars: int | None = None,
    persist_trace: bool = False,
    assistant_message_id: UUID | None = None,
) -> dict:
    settings = get_settings()
    total_start = time.perf_counter()
    timings: dict[str, float] = {}

    normalized_query = normalize_query(query)
    expanded_query = normalized_query
    if session_id and _should_expand_query(normalized_query):
        expanded_query = expand_query_with_history(session_id=session_id, normalized_query=normalized_query, history_turns=settings.chat_history_turns)

    if collection_id:
        collection = collection_model.get_collection(collection_id)
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found.')

    resolved_top_k = min(max(top_k or settings.chat_default_top_k, 1), settings.search_max_limit)
    resolved_score_threshold = score_threshold if score_threshold is not None else settings.chat_default_score_threshold
    resolved_max_context_chunks = max_context_chunks or settings.chat_default_max_context_chunks
    resolved_max_context_chars = max_context_chars or settings.chat_default_max_context_chars
    fetch_k = max(resolved_top_k, settings.chat_retrieval_fetch_k)

    filters = {
        'collection_id': str(collection_id) if collection_id else None,
        'file_id': str(file_id) if file_id else None,
        'source_type': source_type,
    }
    cache_key = build_retrieval_cache_key(
        expanded_query=expanded_query,
        filters=filters,
        top_k=resolved_top_k,
        score_threshold=resolved_score_threshold,
        dedupe=dedupe,
        max_context_chunks=resolved_max_context_chunks,
        max_context_chars=resolved_max_context_chars,
    )
    cached = cache_get_json(cache_key)
    if cached:
        cached_timings = cached.get('timings', {})
        cached_timings['total_ms'] = round((time.perf_counter() - total_start) * 1000, 2)
        cached['timings'] = cached_timings
        cached['cache_hit'] = True
        if persist_trace:
            retrieval_model.create_retrieval_log(
                session_id=session_id,
                user_id=UUID(str(current_identity['id'])),
                assistant_message_id=assistant_message_id,
                query_text=query,
                normalized_query=expanded_query,
                filters=filters,
                top_k=resolved_top_k,
                score_threshold=resolved_score_threshold,
                dedupe_enabled=dedupe,
                hit_count=len(cached.get('items', [])),
                timings=cached_timings,
                metadata={'cache_hit': True, 'candidate_count': cached.get('candidate_count', 0), 'dedupe_removed_count': cached.get('dedupe_removed_count', 0)},
            )
        return cached

    embedding_start = time.perf_counter()
    query_vector = get_cached_query_embedding(expanded_query)
    timings['query_embedding_ms'] = round((time.perf_counter() - embedding_start) * 1000, 2)

    vector_start = time.perf_counter()
    response = get_qdrant_client().query_points(
        collection_name=settings.qdrant_chunks_collection,
        query=query_vector,
        query_filter=build_qdrant_filter(collection_id=collection_id, file_id=file_id, source_type=source_type),
        with_payload=True,
        limit=fetch_k,
        score_threshold=resolved_score_threshold,
    )
    qdrant_points = list(getattr(response, 'points', response) or [])
    timings['vector_search_ms'] = round((time.perf_counter() - vector_start) * 1000, 2)

    chunk_ids = [point.payload.get('chunk_id') for point in qdrant_points if point.payload and point.payload.get('chunk_id')]
    hydrated_rows = retrieval_model.get_chunks_by_ids(chunk_ids)
    rows_by_id = {str(row['id']): row for row in hydrated_rows}

    rerank_start = time.perf_counter()
    ranked_items = rerank_hits(expanded_query=expanded_query, qdrant_points=qdrant_points, rows_by_id=rows_by_id, filters=filters)
    timings['rerank_ms'] = round((time.perf_counter() - rerank_start) * 1000, 2)

    deduped_items, dedupe_removed_count = dedupe_hits(ranked_items, enabled=dedupe)
    context_items = assemble_context(deduped_items, top_k=resolved_top_k, max_context_chunks=resolved_max_context_chunks, max_context_chars=resolved_max_context_chars)
    context_items = assign_citation_labels(context_items)

    result = {
        'query': query,
        'normalized_query': normalized_query,
        'expanded_query': expanded_query,
        'top_k': resolved_top_k,
        'fetch_k': fetch_k,
        'score_threshold': resolved_score_threshold,
        'dedupe': dedupe,
        'candidate_count': len(ranked_items),
        'dedupe_removed_count': dedupe_removed_count,
        'selected_count': len(context_items),
        'items': context_items,
        'filters': filters,
        'timings': timings,
        'cache_hit': False,
    }
    result['timings']['total_ms'] = round((time.perf_counter() - total_start) * 1000, 2)

    cache_set_json(cache_key, result, settings.chat_retrieval_cache_ttl_seconds)

    if persist_trace:
        retrieval_model.create_retrieval_log(
            session_id=session_id,
            user_id=UUID(str(current_identity['id'])),
            assistant_message_id=assistant_message_id,
            query_text=query,
            normalized_query=expanded_query,
            filters=filters,
            top_k=resolved_top_k,
            score_threshold=resolved_score_threshold,
            dedupe_enabled=dedupe,
            hit_count=len(context_items),
            timings=result['timings'],
            metadata={'cache_hit': False, 'candidate_count': len(ranked_items), 'dedupe_removed_count': dedupe_removed_count},
        )

    return result



def normalize_query(query: str) -> str:
    return SPACE_RE.sub(' ', query.strip().lower())



def _should_expand_query(normalized_query: str) -> bool:
    return len(normalized_query) < 48 or any(token in normalized_query for token in {'it', 'that', 'they', 'those', 'this'})



def expand_query_with_history(*, session_id: UUID, normalized_query: str, history_turns: int) -> str:
    recent_messages = chat_model.list_recent_messages_for_session(session_id, history_turns)
    carryover = []
    for message in reversed(recent_messages):
        if message.get('role') != 'user':
            continue
        text = normalize_query(message.get('content', ''))
        if text and text != normalized_query:
            carryover.append(text)
        if len(carryover) >= 2:
            break
    if not carryover:
        return normalized_query
    return f"{' '.join(carryover[-2:])} {normalized_query}".strip()



def build_retrieval_cache_key(**parts) -> str:
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    return f'retrieval:{digest}'



def get_cached_query_embedding(normalized_query: str) -> list[float]:
    settings = get_settings()
    cache_key = f"embedding:{settings.embedding_model_name}:{hashlib.sha256(normalized_query.encode('utf-8')).hexdigest()}"
    cached = cache_get_json(cache_key)
    if cached:
        return [float(value) for value in cached]
    vector = embed_query(normalized_query)
    cache_set_json(cache_key, vector, settings.chat_embedding_cache_ttl_seconds)
    return vector



def build_qdrant_filter(*, collection_id: UUID | None, file_id: UUID | None, source_type: str | None):
    conditions = []
    if collection_id:
        conditions.append(models.FieldCondition(key='collection_id', match=models.MatchValue(value=str(collection_id))))
    if file_id:
        conditions.append(models.FieldCondition(key='file_id', match=models.MatchValue(value=str(file_id))))
    if source_type:
        conditions.append(models.FieldCondition(key='source_type', match=models.MatchValue(value=source_type)))
    if not conditions:
        return None
    return models.Filter(must=conditions)



def rerank_hits(*, expanded_query: str, qdrant_points: list, rows_by_id: dict[str, dict], filters: dict[str, Any]) -> list[dict]:
    query_tokens = tokenize(expanded_query)
    ranked_items = []
    for point in qdrant_points:
        payload = point.payload or {}
        chunk_id = str(payload.get('chunk_id')) if payload.get('chunk_id') else None
        if not chunk_id or chunk_id not in rows_by_id:
            continue
        row = rows_by_id[chunk_id]
        lexical_overlap = lexical_score(query_tokens, tokenize(row.get('content', '')))
        metadata_boost = 0.0
        if filters.get('file_id') and str(row['file_id']) == filters['file_id']:
            metadata_boost += 0.03
        if filters.get('collection_id') and str(row['collection_id']) == filters['collection_id']:
            metadata_boost += 0.02
        rerank_score = float(point.score) * 0.72 + lexical_overlap * 0.23 + metadata_boost
        ranked_items.append(
            {
                'chunk_id': str(row['id']),
                'file_id': str(row['file_id']),
                'filename': row['file_name'],
                'collection_id': str(row['collection_id']),
                'collection_name': row.get('collection_name'),
                'chunk_index': row['chunk_index'],
                'page_number': row.get('page_number'),
                'row_number': row.get('row_number'),
                'source_type': row.get('source_type'),
                'score': round(float(point.score), 6),
                'rerank_score': round(rerank_score, 6),
                'text': row['content'],
                'token_count': row.get('token_count'),
                'content_hash': row.get('content_hash'),
            }
        )
    ranked_items.sort(key=lambda item: item['rerank_score'], reverse=True)
    return ranked_items



def dedupe_hits(items: list[dict], *, enabled: bool) -> tuple[list[dict], int]:
    if not enabled:
        return items, 0
    selected = []
    removed = 0
    seen_hashes: set[str] = set()
    file_positions: dict[str, list[int]] = {}
    for item in items:
        content_hash = item.get('content_hash')
        if content_hash and content_hash in seen_hashes:
            removed += 1
            continue
        positions = file_positions.setdefault(item['file_id'], [])
        if any(abs(existing - int(item['chunk_index'])) <= 1 for existing in positions):
            removed += 1
            continue
        if content_hash:
            seen_hashes.add(content_hash)
        positions.append(int(item['chunk_index']))
        selected.append(item)
    return selected, removed



def assemble_context(*, items: list[dict], top_k: int, max_context_chunks: int, max_context_chars: int) -> list[dict]:
    selected = []
    total_chars = 0
    per_file_counts: Counter[str] = Counter()
    for item in items:
        if len(selected) >= top_k or len(selected) >= max_context_chunks:
            break
        if per_file_counts[item['file_id']] >= 3:
            continue
        next_size = total_chars + len(item['text'])
        if selected and next_size > max_context_chars:
            continue
        selected.append(item)
        per_file_counts[item['file_id']] += 1
        total_chars = next_size
    return selected



def assign_citation_labels(items: list[dict]) -> list[dict]:
    labeled = []
    for index, item in enumerate(items, start=1):
        enriched = dict(item)
        enriched['citation_label'] = f'S{index}'
        enriched['rank'] = index
        labeled.append(enriched)
    return labeled



def tokenize(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))



def lexical_score(query_tokens: set[str], content_tokens: set[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / max(len(query_tokens), 1)
