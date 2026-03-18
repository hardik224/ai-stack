from fastapi import HTTPException, status
from qdrant_client import models

from app.config.settings import get_settings
from app.library.embeddings import embed_query
from app.library.qdrant import get_qdrant_client
from app.models import collection_model, search_model



def search_chunks(*, payload, current_identity: dict) -> dict:
    settings = get_settings()
    limit = min(max(payload.limit, 1), settings.search_max_limit)

    if payload.collection_id:
        collection = collection_model.get_collection(payload.collection_id)
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found.')

    query_vector = embed_query(payload.query.strip())
    client = get_qdrant_client()
    query_filter = _build_filter(payload)

    results = client.search(
        collection_name=settings.qdrant_chunks_collection,
        query_vector=query_vector,
        query_filter=query_filter,
        with_payload=True,
        limit=limit,
        score_threshold=payload.score_threshold,
    )

    chunk_ids = [point.payload.get('chunk_id') for point in results if point.payload and point.payload.get('chunk_id')]
    rows = search_model.get_chunks_by_ids(chunk_ids)
    rows_by_id = {str(row['id']): row for row in rows}

    items = []
    for point in results:
        chunk_id = str(point.payload.get('chunk_id')) if point.payload else None
        if not chunk_id or chunk_id not in rows_by_id:
            continue
        row = rows_by_id[chunk_id]
        items.append(
            {
                'chunk_id': row['id'],
                'file_id': row['file_id'],
                'filename': row['file_name'],
                'collection_id': row['collection_id'],
                'collection_name': row['collection_name'],
                'chunk_index': row['chunk_index'],
                'page_number': row['page_number'],
                'row_number': row['row_number'],
                'source_type': row['source_type'],
                'score': point.score,
                'text': row['content'],
                'token_count': row['token_count'],
            }
        )

    return {
        'query': payload.query,
        'limit': limit,
        'count': len(items),
        'filters': {
            'collection_id': payload.collection_id,
            'file_id': payload.file_id,
        },
        'items': items,
        'auth': {
            'role': current_identity['role'],
            'auth_type': current_identity.get('auth_type', 'session'),
        },
    }



def _build_filter(payload):
    conditions = []
    if payload.collection_id:
        conditions.append(
            models.FieldCondition(
                key='collection_id',
                match=models.MatchValue(value=str(payload.collection_id)),
            )
        )
    if payload.file_id:
        conditions.append(
            models.FieldCondition(
                key='file_id',
                match=models.MatchValue(value=str(payload.file_id)),
            )
        )

    if not conditions:
        return None
    return models.Filter(must=conditions)
