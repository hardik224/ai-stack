import re
from typing import Any
from uuid import UUID

from app.models import retrieval_model


WORD_RE = re.compile(r'[a-z0-9]+')
IDENTIFIER_RE = re.compile(r'[a-z]*\d+[a-z0-9_-]*', re.IGNORECASE)



def retrieve_keyword_candidates(
    *,
    query_text: str,
    collection_id: UUID | None,
    file_id: UUID | None,
    source_type: str | None,
    limit: int,
) -> list[dict]:
    rows = retrieval_model.search_keyword_chunks(
        query_text=query_text,
        collection_id=collection_id,
        file_id=file_id,
        source_type=source_type,
        limit=limit,
    )
    query_tokens = tokenize(query_text)
    lowered_query = query_text.lower()
    identifier_terms = IDENTIFIER_RE.findall(lowered_query)

    items = []
    for rank, row in enumerate(rows, start=1):
        text = row.get('content', '') or ''
        filename = row.get('file_name', '') or ''
        lexical_overlap = lexical_score(query_tokens, tokenize(text))
        filename_lower = filename.lower()
        match_reasons = []
        if row.get('filename_match'):
            match_reasons.append('filename_match')
        if row.get('phrase_match'):
            match_reasons.append('content_phrase_match')
        if any(identifier in text.lower() or identifier in filename_lower for identifier in identifier_terms):
            match_reasons.append('identifier_match')

        items.append(
            {
                'chunk_id': str(row['id']),
                'file_id': str(row['file_id']),
                'filename': filename,
                'collection_id': str(row['collection_id']),
                'collection_name': row.get('collection_name'),
                'chunk_index': row['chunk_index'],
                'page_number': row.get('page_number'),
                'row_number': row.get('row_number'),
                'source_type': row.get('source_type'),
                'source_metadata': row.get('source_metadata') or {},
                'document_title': (row.get('source_metadata') or {}).get('document_title'),
                'text': text,
                'token_count': row.get('token_count'),
                'content_hash': row.get('content_hash'),
                'score': 0.0,
                'vector_score': 0.0,
                'keyword_score': round(float(row.get('keyword_rank_score') or 0.0), 6),
                'simple_rank': round(float(row.get('simple_rank') or 0.0), 6),
                'english_rank': round(float(row.get('english_rank') or 0.0), 6),
                'filename_similarity': round(float(row.get('filename_similarity') or 0.0), 6),
                'lexical_overlap': round(lexical_overlap, 6),
                'match_reasons': match_reasons,
                'retrieval_sources': ['keyword'],
                'vector_rank': None,
                'keyword_rank': rank,
            }
        )
    return items



def tokenize(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))



def lexical_score(query_tokens: set[str], content_tokens: set[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / max(len(query_tokens), 1)
