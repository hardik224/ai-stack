from app.services import retrieval_service



def search_chunks(*, payload, current_identity: dict) -> dict:
    retrieval = retrieval_service.retrieve_chunks(
        query=payload.query,
        current_identity=current_identity,
        session_id=payload.session_id,
        collection_id=payload.collection_id,
        file_id=payload.file_id,
        source_type=payload.source_type,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        dedupe=payload.dedupe,
        enable_vector=payload.enable_vector,
        enable_keyword=payload.enable_keyword,
        enable_rerank=payload.enable_rerank,
        max_context_chunks=payload.max_context_chunks,
        max_context_chars=payload.max_context_chars,
        persist_trace=True,
        debug=payload.debug,
    )
    response = {
        'query': retrieval['query'],
        'normalized_query': retrieval['normalized_query'],
        'expanded_query': retrieval['expanded_query'],
        'top_k': retrieval['top_k'],
        'fetch_k': retrieval['fetch_k'],
        'vector_fetch_k': retrieval.get('vector_fetch_k', 0),
        'keyword_fetch_k': retrieval.get('keyword_fetch_k', 0),
        'count': len(retrieval['items']),
        'filters': retrieval['filters'],
        'items': retrieval['items'],
        'timings': retrieval['timings'],
        'dedupe': {
            'enabled': retrieval['dedupe'],
            'removed_count': retrieval['dedupe_removed_count'],
        },
        'stats': {
            'candidate_count': retrieval['candidate_count'],
            'selected_count': retrieval['selected_count'],
            'cache_hit': retrieval['cache_hit'],
            **retrieval.get('stats', {}),
        },
        'paths': retrieval.get('paths', {}),
        'fusion': retrieval.get('fusion', {}),
        'rerank': retrieval.get('rerank', {}),
        'evidence_assessment': retrieval.get('evidence_assessment', {}),
        'media_suggestions': retrieval.get('media_suggestions') or [],
        'cache': retrieval.get('cache', {}),
        'cache_version_scope': retrieval.get('cache_version_scope', {}),
        'auth': {
            'role': current_identity['role'],
            'auth_type': current_identity.get('auth_type', 'session'),
        },
    }
    if payload.debug:
        response['debug'] = retrieval.get('debug', {})
    return response
