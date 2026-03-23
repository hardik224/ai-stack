import re
import time
from collections import Counter
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from qdrant_client import models

from app.config.settings import get_settings
from app.library import cache
from app.library.embeddings import embed_query
from app.library.qdrant import get_qdrant_client
from app.models import chat_model, collection_model, retrieval_model
from app.services import fusion_service, keyword_service, media_card_service, reranker_service


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
    cache_info = {
        'retrieval': {'hit': False, 'lookup_ms': 0.0, 'ttl_seconds': None},
        'embedding': {'hit': False, 'lookup_ms': 0.0, 'ttl_seconds': None},
    }

    normalized_query = normalize_query(query)
    expanded_query = normalized_query
    if session_id and _should_expand_query(normalized_query):
        expanded_query = expand_query_with_history(
            session_id=session_id,
            normalized_query=normalized_query,
            history_turns=settings.chat_history_turns,
        )

    effective_collection_id = _resolve_collection_scope(collection_id=collection_id, file_id=file_id)
    if effective_collection_id:
        collection = collection_model.get_collection(UUID(str(effective_collection_id)))
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
    version_scope = cache.get_retrieval_cache_scope(collection_id=effective_collection_id)
    retrieval_signature = {
        'expanded_query': expanded_query,
        'filters': filters,
        'top_k': resolved_top_k,
        'score_threshold': resolved_score_threshold,
        'dedupe': dedupe,
        'enable_vector': enable_vector,
        'enable_keyword': enable_keyword,
        'enable_rerank': resolved_enable_rerank,
        'max_context_chunks': resolved_max_context_chunks,
        'max_context_chars': resolved_max_context_chars,
    }

    cached, retrieval_cache_meta = cache.get_cached_retrieval(signature=retrieval_signature, version_scope=version_scope)
    timings['retrieval_cache_lookup_ms'] = retrieval_cache_meta['lookup_ms']
    cache_info['retrieval'] = {
        **retrieval_cache_meta,
        'ttl_seconds': cache.get_ttl(retrieval_cache_meta['key']),
    }
    if cached:
        cached_timings = dict(cached.get('timings', {}))
        cached_timings['retrieval_cache_lookup_ms'] = retrieval_cache_meta['lookup_ms']
        cached_timings['total_ms'] = round((time.perf_counter() - total_start) * 1000, 2)
        cached['timings'] = cached_timings
        cached['cache_hit'] = True
        cached['cache'] = dict(cached.get('cache', {}))
        cached['cache']['retrieval'] = cache_info['retrieval']
        if 'evidence_assessment' not in cached:
            cached['evidence_assessment'] = assess_evidence(cached.get('items', []))
        if not cached.get('media_suggestions'):
            cached['media_suggestions'] = media_card_service.choose_media_suggestions(cached.get('items', []), question=expanded_query)
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

    if enable_vector:
        embedding_cache_payload, embedding_cache_meta = cache.get_cached_embedding(
            normalized_query=expanded_query,
            model_name=settings.embedding_model_name,
        )
        timings['embedding_cache_lookup_ms'] = embedding_cache_meta['lookup_ms']
        cache_info['embedding'] = {
            **embedding_cache_meta,
            'ttl_seconds': cache.get_ttl(embedding_cache_meta['key']),
        }
        embedding_start = time.perf_counter()
        if embedding_cache_payload is not None:
            query_vector = [float(value) for value in embedding_cache_payload]
        else:
            query_vector = embed_query(expanded_query)
            cache.set_cached_embedding(
                normalized_query=expanded_query,
                model_name=settings.embedding_model_name,
                vector=query_vector,
            )
            cache_info['embedding']['ttl_seconds'] = settings.cache_embedding_ttl_seconds
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
        timings['embedding_cache_lookup_ms'] = 0.0
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
        query=expanded_query,
        top_k=resolved_top_k,
        max_context_chunks=resolved_max_context_chunks,
        max_context_chars=resolved_max_context_chars,
    )
    context_items = assign_citation_labels(context_items)
    timings['context_assembly_ms'] = round((time.perf_counter() - context_start) * 1000, 2)
    evidence_assessment = assess_evidence(context_items)
    media_suggestions = media_card_service.choose_media_suggestions(context_items, question=expanded_query)

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
        'cache': cache_info,
        'cache_version_scope': version_scope,
        'retrieval_signature': cache.build_hash(retrieval_signature),
        'evidence_assessment': evidence_assessment,
        'media_suggestions': media_suggestions,
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

    cache.set_cached_retrieval(signature=retrieval_signature, version_scope=version_scope, payload=result)
    result['cache']['retrieval']['ttl_seconds'] = settings.cache_retrieval_ttl_seconds

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
    tokens = normalized_query.split()
    followup_phrases = (
        'what about', 'how about', 'tell me more', 'go deeper', 'explain more', 'and also', 'what else', 'why is', 'how is'
    )
    followup_terms = {'it', 'that', 'they', 'those', 'this', 'these', 'he', 'she', 'them', 'more', 'else', 'then'}
    return (
        len(normalized_query) <= 96 and len(tokens) <= 12
        or any(phrase in normalized_query for phrase in followup_phrases)
        or any(token in followup_terms for token in tokens)
    )



def expand_query_with_history(*, session_id: UUID, normalized_query: str, history_turns: int) -> str:
    recent_messages = chat_model.list_recent_messages_for_session(session_id, max(history_turns * 2, 8))
    carryover: list[str] = []
    for message in reversed(recent_messages):
        role = message.get('role')
        if role not in {'user', 'assistant'}:
            continue
        text = normalize_query(message.get('content', ''))
        if not text or text == normalized_query:
            continue
        label = 'prior user context' if role == 'user' else 'prior assistant context'
        carryover.append(f"{label}: {text[:220]}")
        if len(carryover) >= 3:
            break
    if not carryover:
        return normalized_query
    return f"{' | '.join(reversed(carryover))} | current question: {normalized_query}".strip()



def _resolve_collection_scope(*, collection_id: UUID | None, file_id: UUID | None) -> str | None:
    if collection_id:
        return str(collection_id)
    if not file_id:
        return None
    return retrieval_model.get_file_collection_id(file_id)



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
                'source_metadata': row.get('source_metadata') or {},
                'document_title': (row.get('source_metadata') or {}).get('document_title'),
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
        metadata = item.get('source_metadata') or {}
        location_key = (
            item['file_id'],
            item.get('source_type') or 'unknown',
            item.get('page_number'),
            item.get('row_number'),
            metadata.get('chunk_type'),
            metadata.get('start'),
            metadata.get('end'),
            metadata.get('json_path'),
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



def assemble_context(*, items: list[dict], query: str, top_k: int, max_context_chunks: int, max_context_chars: int) -> list[dict]:
    selected: list[dict] = []
    total_chars = 0
    per_file_counts: Counter[str] = Counter()
    selected_chunk_indexes: dict[str, list[int]] = {}
    used_indexes: set[int] = set()
    synthesis_query = _is_synthesis_query(query)
    target_diverse_count = max(1, min(top_k, max_context_chunks, 3 if synthesis_query else 2))

    def add_item(index: int, item: dict) -> bool:
        nonlocal total_chars
        if index in used_indexes:
            return False
        if len(selected) >= top_k or len(selected) >= max_context_chunks:
            return False
        if not _can_add_context_item(selected=selected, item=item, total_chars=total_chars, max_context_chars=max_context_chars):
            return False
        selected.append(item)
        used_indexes.add(index)
        per_file_counts[item['file_id']] += 1
        selected_chunk_indexes.setdefault(item['file_id'], []).append(int(item['chunk_index']))
        total_chars += len(item.get('text', ''))
        return True

    for index, item in enumerate(items):
        if len(selected) >= target_diverse_count:
            break
        if per_file_counts[item['file_id']] >= 1:
            continue
        add_item(index, item)

    for index, item in enumerate(items):
        if len(selected) >= top_k or len(selected) >= max_context_chunks:
            break
        if index in used_indexes:
            continue
        if per_file_counts[item['file_id']] >= (3 if synthesis_query else 2):
            continue
        if synthesis_query and per_file_counts[item['file_id']] == 0:
            add_item(index, item)
            continue
        if _is_adjacent_support(item=item, selected_chunk_indexes=selected_chunk_indexes):
            add_item(index, item)
            continue
        if float(item.get('rerank_score', 0.0)) >= 0.55 or len(item.get('retrieval_sources', [])) > 1:
            add_item(index, item)

    for index, item in enumerate(items):
        if len(selected) >= top_k or len(selected) >= max_context_chunks:
            break
        if index in used_indexes:
            continue
        if per_file_counts[item['file_id']] >= 3:
            continue
        add_item(index, item)

    return selected



def _is_synthesis_query(query: str) -> bool:
    lowered = query.lower()
    cues = (
        'compare', 'difference', 'different', 'across', 'combine', 'combined', 'summarize', 'summary',
        'analyze', 'analysis', 'relationship', 'impact', 'why', 'how', 'workflow', 'process', 'steps',
        'risk', 'recommend', 'explain', 'together'
    )
    return any(cue in lowered for cue in cues)



def _is_adjacent_support(*, item: dict, selected_chunk_indexes: dict[str, list[int]]) -> bool:
    indexes = selected_chunk_indexes.get(item['file_id'], [])
    current_index = int(item['chunk_index'])
    return any(abs(existing - current_index) <= 2 for existing in indexes)



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
            'source_diversity': 0,
        }

    top_rerank_score = max(float(item.get('rerank_score', 0.0)) for item in items)
    top_fused_score = max(float(item.get('fused_score', 0.0)) for item in items)
    top_vector_score = max(float(item.get('vector_score', item.get('score', 0.0))) for item in items)
    top_keyword_score = max(float(item.get('keyword_score', 0.0)) for item in items)
    max_lexical_overlap = max(float(item.get('lexical_overlap', 0.0)) for item in items)
    selected_count = len(items)

    has_min_items = selected_count >= settings.chat_min_grounding_items
    has_strong_rerank = top_rerank_score >= settings.chat_min_grounding_score
    has_strong_semantic = top_vector_score >= max(settings.chat_default_score_threshold + 0.12, 0.34)
    has_strong_keyword = top_keyword_score >= 0.2 and max_lexical_overlap >= max(settings.chat_min_grounding_lexical_overlap * 0.5, 0.04)

    is_sufficient = has_min_items and (
        (has_strong_rerank and max_lexical_overlap >= max(settings.chat_min_grounding_lexical_overlap * 0.5, 0.04))
        or has_strong_semantic
        or has_strong_keyword
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
        'has_strong_rerank': has_strong_rerank,
        'has_strong_semantic': has_strong_semantic,
        'has_strong_keyword': has_strong_keyword,
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
            'cache': result.get('cache', {}),
            'cache_version_scope': result.get('cache_version_scope', {}),
            'candidate_count': result.get('candidate_count', 0),
            'dedupe_removed_count': result.get('dedupe_removed_count', 0),
            'evidence_assessment': result.get('evidence_assessment', {}),
            'paths': result.get('paths', {}),
            'stats': result.get('stats', {}),
            'fusion': result.get('fusion', {}),
            'rerank': result.get('rerank', {}),
            'debug': result.get('debug', {}),
            'retrieval_signature': result.get('retrieval_signature'),
        },
    )



def tokenize(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))



def lexical_score(query_tokens: set[str], content_tokens: set[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / max(len(query_tokens), 1)
