from uuid import UUID

from qdrant_client import models

from app.config.settings import get_settings
from app.library.qdrant import upsert_points



def upsert_chunk_vectors(*, file_id: UUID, collection_id: UUID, file_name: str, chunks: list[dict]) -> None:
    settings = get_settings()
    batch_size = max(settings.indexing_batch_size, 1)

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        points = [
            models.PointStruct(
                id=str(chunk['qdrant_point_id']),
                vector=chunk['embedding'],
                payload={
                    'chunk_id': str(chunk['id']),
                    'file_id': str(file_id),
                    'collection_id': str(collection_id),
                    'file_name': file_name,
                    'source_type': chunk['source_type'],
                    'chunk_index': chunk['chunk_index'],
                    'page_number': chunk['page_number'],
                    'row_number': chunk['row_number'],
                    'content_hash': chunk['content_hash'],
                    'chunk_type': (chunk.get('source_metadata') or {}).get('chunk_type'),
                    'video_id': (chunk.get('source_metadata') or {}).get('video_id'),
                    'document_title': (chunk.get('source_metadata') or {}).get('document_title'),
                    'segment_start': (chunk.get('source_metadata') or {}).get('start'),
                    'segment_end': (chunk.get('source_metadata') or {}).get('end'),
                    'deep_link_url': (chunk.get('source_metadata') or {}).get('deep_link_url'),
                },
            )
            for chunk in batch
        ]
        upsert_points(points)
