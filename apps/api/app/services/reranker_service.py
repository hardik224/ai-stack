import re
from typing import Any

from app.config.settings import get_settings


WORD_RE = re.compile(r'[a-z0-9]+')
IDENTIFIER_RE = re.compile(r'[a-z]*\d+[a-z0-9_-]*', re.IGNORECASE)



def rerank_candidates(*, query: str, candidates: list[dict], filters: dict[str, Any], enabled: bool | None = None) -> tuple[list[dict], dict]:
    settings = get_settings()
    resolved_enabled = settings.rerank_enabled if enabled is None else enabled
    provider = settings.rerank_provider
    if not resolved_enabled or provider == 'disabled':
        items = []
        for rank, item in enumerate(candidates, start=1):
            enriched = dict(item)
            enriched['rerank_score'] = round(float(item.get('fused_score', item.get('vector_score', 0.0))), 6)
            enriched['rank'] = rank
            items.append(enriched)
        return items, {'enabled': False, 'provider': provider}

    if provider != 'heuristic':
        provider = 'heuristic'

    query_tokens = tokenize(query)
    query_lower = query.lower()
    identifier_terms = IDENTIFIER_RE.findall(query_lower)
    reranked = []
    for item in candidates[: max(settings.rerank_max_candidates, 1)]:
        text_lower = item.get('text', '').lower()
        filename_lower = item.get('filename', '').lower()
        lexical_overlap = max(float(item.get('lexical_overlap', 0.0)), lexical_score(query_tokens, tokenize(text_lower)))
        exact_phrase_boost = 0.14 if query_lower in text_lower else 0.0
        filename_exact_boost = 0.12 if query_lower in filename_lower else 0.0
        identifier_boost = 0.0
        if identifier_terms and any(term in text_lower or term in filename_lower for term in identifier_terms):
            identifier_boost = 0.10
        metadata_boost = 0.0
        if filters.get('file_id') and item.get('file_id') == filters['file_id']:
            metadata_boost += 0.04
        if filters.get('collection_id') and item.get('collection_id') == filters['collection_id']:
            metadata_boost += 0.02
        source_blend_boost = 0.03 if len(item.get('retrieval_sources', [])) > 1 else 0.0
        rerank_score = (
            float(item.get('fused_score', 0.0)) * 0.42
            + float(item.get('vector_score', item.get('score', 0.0))) * 0.20
            + float(item.get('keyword_score', 0.0)) * 0.18
            + lexical_overlap * 0.12
            + exact_phrase_boost
            + filename_exact_boost
            + identifier_boost
            + metadata_boost
            + source_blend_boost
        )
        enriched = dict(item)
        enriched['lexical_overlap'] = round(lexical_overlap, 6)
        enriched['rerank_score'] = round(rerank_score, 6)
        reranked.append(enriched)

    reranked.sort(
        key=lambda item: (
            item.get('rerank_score', 0.0),
            item.get('fused_score', 0.0),
            item.get('keyword_score', 0.0),
            item.get('vector_score', 0.0),
        ),
        reverse=True,
    )
    for index, item in enumerate(reranked, start=1):
        item['rank'] = index
    return reranked, {'enabled': True, 'provider': provider}



def tokenize(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))



def lexical_score(query_tokens: set[str], content_tokens: set[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / max(len(query_tokens), 1)
