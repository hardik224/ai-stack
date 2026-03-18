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
from app.services import fusion_service, keyword_service, reranker_service


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
    enable_vector: bool = True,
    enable_keyword: bool = True,
    enable_rerank: bool | None = None,
    max_context_chunks: int | None = None,
    max_context_chars: int | None = None,
    persist_trace: bool = False,
    assistant_message_id: UUID | None = None,
    debug: bool = False,
) -> dict:
    settings = get_settings()
    total_start = time.perf_counter()
    timings: dict[str, float] = {}

    normalized_query = normalize_query(query)
    expanded_query = normalized_query
    if session_id and _should_expand_query(normalized_query):
        expanded_query = expand_query_with_history(
            session_id=session_id,
            normalized_query=normalized_query,
            history_turns=settings.chat_history_turns,
        )

    if collection_id:
        collection = collection_model.get_collection(collection_id)
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found.')

    resolved_top_k = min(max(top_k or settings.chat_default_top_k, 1), settings.search_max_limit)
    resolved_score_threshold = score_threshold if score_threshold is not None else settings.chat_default_score_threshold
    resolved_max_context_chunks = max_context_chunks or settings.chat_default_max_context_chunks
    resolved_max_context_chars = max_context_chars or settings.chat_default_max_context_chars
    vector_fetch_k = max(resolved_top_k, settings.chat_retrieval_fetch_k)
    keyword_fetch_k = max(resolved_top_k, settings.hybrid_keyword_fetch_k)
    resolved_enable_rerank = settings.rerank_enabled if enable_rerank is None else enable_rerank

    if not enable_vector and not enable_keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='At least one retrieval path must be enabled.')

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
        enable_vector=enable_vector,
        enable_keyword=enable_keyword,
        enable_rerank=resolved_enable_rerank,
        max_context_chunks=resolved_max_context_chunks,
        max_context_chars=resolved_max_context_chars,
    )
    cached = cache_get_json(cache_key)
    if cached:
        cached_timings = dict(cached.get('timings', {}))
        cached_timings['total_ms'] = round((time.perf_counter() - total_start) * 1000, 2)
        cached['timings'] = cached_timings
        cached['cache_hit'] = True
        if 'evidence_assessment' not in cached:
            cached['evidence_assessment'] = assess_evidence(cached.get('items', []))
        if persist_trace:
            _persist_retrieval_trace(
                session_id=session_id,
                current_identity=current_identity,
                assistant_message_id=assistant_message_id,
                query=query,
                normalized_query=expanded_query,
                filters=filters,
                top_k=resolved_top_k,
                score_threshold=resolved_score_threshold,
                dedupe=dedupe,
                timings=cached_timings,
                result=cached,
            )
        if not debug and 'debug' in cached:
            cached['debug'] = {
                'vector_top_chunk_ids': cached['debug'].get('vector_top_chunk_ids', []),
                'keyword_top_chunk_ids': cached['debug'].get('keyword_top_chunk_ids', []),
                'selected_chunk_ids': cached['debug'].get('selected_chunk_ids', []),
            }
        return cached

    vector_items: list[dict] = []
    keyword_items: list[dict] = []
    query_vector: list[float] | None = None

    if enable_vector:
        embedding_start = time.perf_counter()
        query_vector = get_cached_query_embedding(expanded_query)
        timings['query_embedding_ms'] = round((time.perf_counter() - embedding_start) * 1000, 2)

        vector_start = time.perf_counter()
        response = get_qdrant_client().query_points(
            collection_name=settings.qdrant_chunks_collection,
            query=query_vector,
            query_filter=build_qdrant_filter(collection_id=collection_id, file_id=file_id, source_type=source_type),
            with_payload=True,
            limit=vector_fetch_k,
            score_threshold=resolved_score_threshold,
        )
        qdrant_points = list(getattr(response, 'points', response) or [])
        timings['vector_search_ms'] = round((time.perf_counter() - vector_start) * 1000, 2)

        chunk_ids = [point.payload.get('chunk_id') for point in qdrant_points if point.payload and point.payload.get('chunk_id')]
        hydrated_rows = retrieval_model.get_chunks_by_ids(chunk_ids)
        rows_by_id = {str(row['id']): row for row in hydrated_rows}
        vector_items = build_vector_candidates(
            expanded_query=expanded_query,
            qdrant_points=qdrant_points,
            rows_by_id=rows_by_id,
            filters=filters,
        )
    else:
        timings['query_embedding_ms'] = 0.0
        timings['vector_search_ms'] = 0.0

    if enable_keyword:
        keyword_start = time.perf_counter()
        keyword_items = keyword_service.retrieve_keyword_candidates(
            query_text=expanded_query,
            collection_id=collection_id,
            file_id=file_id,
            source_type=source_type,
            limit=keyword_fetch_k,
        )
        timings['keyword_search_ms'] = round((time.perf_counter() - keyword_start) * 1000, 2)
    else:
        timings['keyword_search_ms'] = 0.0

    fusion_start = time.perf_counter()
    fused_items = fusion_service.fuse_candidates(
        vector_items=vector_items,
        keyword_items=keyword_items,
        rrf_k=settings.hybrid_rrf_k,
        vector_weight=settings.hybrid_vector_weight,
        keyword_weight=settings.hybrid_keyword_weight,
    )
    timings['fusion_ms'] = round((time.perf_counter() - fusion_start) * 1000, 2)

    rerank_start = time.perf_counter()
    reranked_items, rerank_metadata = reranker_service.rerank_candidates(
        query=expanded_query,
        candidates=fused_items,
        filters=filters,
        enabled=resolved_enable_rerank,
    )
    timings['rerank_ms'] = round((time.perf_counter() - rerank_start) * 1000, 2)

    deduped_items, dedupe_removed_count = dedupe_hits(reranked_items, enabled=dedupe)
    context_start = time.perf_counter()
    context_items = assemble_context(
        items=deduped_items,
        top_k=resolved_top_k,
        max_context_chunks=resolved_max_context_chunks,
        max_context_chars=resolved_max_context_chars,
    )
    context_items = assign_citation_labels(context_items)
    timings['context_assembly_ms'] = round((time.perf_counter() - context_start) * 1000, 2)
    evidence_assessment = assess_evidence(context_items)

    result = {
        'query': query,
        'normalized_query': normalized_query,
        'expanded_query': expanded_query,
        'top_k': resolved_top_k,
        'fetch_k': max(vector_fetch_k if enable_vector else 0, keyword_fetch_k if enable_keyword else 0),
        'vector_fetch_k': vector_fetch_k if enable_vector else 0,
        'keyword_fetch_k': keyword_fetch_k if enable_keyword else 0,
        'score_threshold': resolved_score_threshold,
        'dedupe': dedupe,
        'candidate_count': len(fused_items),
        'dedupe_removed_count': dedupe_removed_count,
        'selected_count': len(context_items),
        'items': context_items,
        'filters': filters,
        'timings': timings,
        'cache_hit': False,
        'evidence_assessment': evidence_assessment,
        'paths': {
            'vector_enabled': enable_vector,
            'keyword_enabled': enable_keyword,
            'rerank_enabled': resolved_enable_rerank,
        },
        'stats': {
            'vector_candidate_count': len(vector_items),
            'keyword_candidate_count': len(keyword_items),
            'fusion_candidate_count': len(fused_items),
            'reranked_candidate_count': len(reranked_items),
            'selected_count': len(context_items),
        },
        'fusion': {
            'strategy': 'weighted_rrf',
            'rrf_k': settings.hybrid_rrf_k,
            'vector_weight': settings.hybrid_vector_weight,
            'keyword_weight': settings.hybrid_keyword_weight,
        },
        'rerank': rerank_metadata,
        'debug': {
            'vector_top_chunk_ids': [item['chunk_id'] for item in vector_items[:5]],
            'keyword_top_chunk_ids': [item['chunk_id'] for item in keyword_items[:5]],
            'fused_top_chunk_ids': [item['chunk_id'] for item in fused_items[:5]],
            'selected_chunk_ids': [item['chunk_id'] for item in context_items],
        },
    }
    result['timings']['total_ms'] = round((time.perf_counter() - total_start) * 1000, 2)

    cache_set_json(cache_key, result, settings.chat_retrieval_cache_ttl_seconds)

    if persist_trace:
        _persist_retrieval_trace(
            session_id=session_id,
            current_identity=current_identity,
            assistant_message_id=assistant_message_id,
            query=query,
            normalized_query=expanded_query,
            filters=filters,
            top_k=resolved_top_k,
            score_threshold=resolved_score_threshold,
            dedupe=dedupe,
            timings=result['timings'],
            result=result,
        )

    if not debug:
        result['debug'] = {
            'vector_top_chunk_ids': result['debug']['vector_top_chunk_ids'],
            'keyword_top_chunk_ids': result['debug']['keyword_top_chunk_ids'],
            'selected_chunk_ids': result['debug']['selected_chunk_ids'],
        }

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



def build_vector_candidates(*, expanded_query: str, qdrant_points: list, rows_by_id: dict[str, dict], filters: dict[str, Any]) -> list[dict]:
    query_tokens = tokenize(expanded_query)
    ranked_items = []
    for rank, point in enumerate(qdrant_points, start=1):
        payload = point.payload or {}
        chunk_id = str(payload.get('chunk_id')) if payload.get('chunk_id') else None
        if not chunk_id or chunk_id not in rows_by_id:
            continue
        row = rows_by_id[chunk_id]
        lexical_overlap = lexical_score(query_tokens, tokenize(row.get('content', '')))
        match_reasons = []
        if filters.get('file_id') and str(row['file_id']) == filters['file_id']:
            match_reasons.append('file_filter_match')
        if filters.get('collection_id') and str(row['collection_id']) == filters['collection_id']:
            match_reasons.append('collection_filter_match')
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
                'vector_score': round(float(point.score), 6),
                'keyword_score': 0.0,
                'lexical_overlap': round(lexical_overlap, 6),
                'text': row['content'],
                'token_count': row.get('token_count'),
                'content_hash': row.get('content_hash'),
                'match_reasons': match_reasons,
                'retrieval_sources': ['vector'],
                'vector_rank': rank,
                'keyword_rank': None,
            }
        )
    return ranked_items



def dedupe_hits(items: list[dict], *, enabled: bool) -> tuple[list[dict], int]:
    if not enabled:
        return items, 0
    selected = []
    removed = 0
    seen_hashes: set[str] = set()
    file_positions: dict[str, list[int]] = {}
    seen_locations: set[tuple[str, str, int | None, int | None]] = set()
    for item in items:
        content_hash = item.get('content_hash')
        if content_hash and content_hash in seen_hashes:
            removed += 1
            continue
        location_key = (
            item['file_id'],
            item.get('source_type') or 'unknown',
            item.get('page_number'),
            item.get('row_number'),
        )
        if location_key in seen_locations:
            removed += 1
            continue
        positions = file_positions.setdefault(item['file_id'], [])
        chunk_index = int(item['chunk_index'])
        if any(abs(existing - chunk_index) <= 1 for existing in positions):
            removed += 1
            continue
        if content_hash:
            seen_hashes.add(content_hash)
        positions.append(chunk_index)
        seen_locations.add(location_key)
        selected.append(item)
    return selected, removed



def assemble_context(*, items: list[dict], top_k: int, max_context_chunks: int, max_context_chars: int) -> list[dict]:
    selected: list[dict] = []
    total_chars = 0
    per_file_counts: Counter[str] = Counter()
    used_indexes: set[int] = set()
    target_diverse_count = max(1, min(top_k, max_context_chunks) // 2)

    for index, item in enumerate(items):
        if len(selected) >= target_diverse_count:
            break
        if per_file_counts[item['file_id']] >= 1:
            continue
        if not _can_add_context_item(selected=selected, item=item, total_chars=total_chars, max_context_chars=max_context_chars):
            continue
        selected.append(item)
        used_indexes.add(index)
        per_file_counts[item['file_id']] += 1
        total_chars += len(item.get('text', ''))

    for index, item in enumerate(items):
        if index in used_indexes:
            continue
        if len(selected) >= top_k or len(selected) >= max_context_chunks:
            break
        if per_file_counts[item['file_id']] >= 3:
            continue
        if not _can_add_context_item(selected=selected, item=item, total_chars=total_chars, max_context_chars=max_context_chars):
            continue
        selected.append(item)
        per_file_counts[item['file_id']] += 1
        total_chars += len(item.get('text', ''))

    return selected



def _can_add_context_item(*, selected: list[dict], item: dict, total_chars: int, max_context_chars: int) -> bool:
    next_size = total_chars + len(item.get('text', ''))
    if selected and next_size > max_context_chars:
        return False
    return True



def assign_citation_labels(items: list[dict]) -> list[dict]:
    labeled = []
    for index, item in enumerate(items, start=1):
        enriched = dict(item)
        enriched['citation_label'] = f'S{index}'
        enriched['rank'] = index
        labeled.append(enriched)
    return labeled



def assess_evidence(items: list[dict]) -> dict:
    settings = get_settings()
    if not items:
        return {
            'is_sufficient': False,
            'reason': 'no_grounded_evidence',
            'selected_count': 0,
            'top_rerank_score': 0.0,
            'top_fused_score': 0.0,
            'top_vector_score': 0.0,
            'top_keyword_score': 0.0,
            'max_lexical_overlap': 0.0,
        }

    top_rerank_score = max(float(item.get('rerank_score', 0.0)) for item in items)
    top_fused_score = max(float(item.get('fused_score', 0.0)) for item in items)
    top_vector_score = max(float(item.get('vector_score', item.get('score', 0.0))) for item in items)
    top_keyword_score = max(float(item.get('keyword_score', 0.0)) for item in items)
    max_lexical_overlap = max(float(item.get('lexical_overlap', 0.0)) for item in items)
    selected_count = len(items)

    is_sufficient = (
        selected_count >= settings.chat_min_grounding_items
        and top_rerank_score >= settings.chat_min_grounding_score
        and max_lexical_overlap >= settings.chat_min_grounding_lexical_overlap
    )

    reason = 'grounded_evidence_sufficient' if is_sufficient else 'grounded_evidence_too_weak'
    return {
        'is_sufficient': is_sufficient,
        'reason': reason,
        'selected_count': selected_count,
        'top_rerank_score': round(top_rerank_score, 6),
        'top_fused_score': round(top_fused_score, 6),
        'top_vector_score': round(top_vector_score, 6),
        'top_keyword_score': round(top_keyword_score, 6),
        'max_lexical_overlap': round(max_lexical_overlap, 6),
    }



def _persist_retrieval_trace(
    *,
    session_id: UUID | None,
    current_identity: dict,
    assistant_message_id: UUID | None,
    query: str,
    normalized_query: str,
    filters: dict,
    top_k: int,
    score_threshold: float | None,
    dedupe: bool,
    timings: dict,
    result: dict,
) -> None:
    retrieval_model.create_retrieval_log(
        session_id=session_id,
        user_id=UUID(str(current_identity['id'])),
        assistant_message_id=assistant_message_id,
        query_text=query,
        normalized_query=normalized_query,
        filters=filters,
        top_k=top_k,
        score_threshold=score_threshold,
        dedupe_enabled=dedupe,
        hit_count=len(result.get('items', [])),
        timings=timings,
        metadata={
            'cache_hit': result.get('cache_hit', False),
            'candidate_count': result.get('candidate_count', 0),
            'dedupe_removed_count': result.get('dedupe_removed_count', 0),
            'evidence_assessment': result.get('evidence_assessment', {}),
            'paths': result.get('paths', {}),
            'stats': result.get('stats', {}),
            'fusion': result.get('fusion', {}),
            'rerank': result.get('rerank', {}),
            'debug': result.get('debug', {}),
        },
    )



def tokenize(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))



def lexical_score(query_tokens: set[str], content_tokens: set[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / max(len(query_tokens), 1)
