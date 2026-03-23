from qdrant_client import QdrantClient, models

from app.config.settings import Settings, get_settings
from app.library.embeddings import get_vector_size


_client: QdrantClient | None = None


def init_qdrant_client(settings: Settings) -> None:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)


def get_qdrant_client() -> QdrantClient:
    if _client is None:
        raise RuntimeError('Qdrant client has not been initialized.')
    return _client


def close_qdrant_client() -> None:
    global _client
    if _client is not None:
        close_method = getattr(_client, 'close', None)
        if callable(close_method):
            close_method()
        _client = None


def ensure_chunks_collection() -> None:
    settings = get_settings()
    client = get_qdrant_client()
    vector_size = get_vector_size()

    try:
        client.get_collection(settings.qdrant_chunks_collection)
    except Exception:
        client.create_collection(
            collection_name=settings.qdrant_chunks_collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    for field_name, field_schema in (
        ('collection_id', models.PayloadSchemaType.KEYWORD),
        ('file_id', models.PayloadSchemaType.KEYWORD),
        ('source_type', models.PayloadSchemaType.KEYWORD),
        ('page_number', models.PayloadSchemaType.INTEGER),
        ('row_number', models.PayloadSchemaType.INTEGER),
        ('chunk_type', models.PayloadSchemaType.KEYWORD),
        ('video_id', models.PayloadSchemaType.KEYWORD),
    ):
        try:
            client.create_payload_index(
                collection_name=settings.qdrant_chunks_collection,
                field_name=field_name,
                field_schema=field_schema,
            )
        except Exception:
            pass


def delete_file_points(file_id: str) -> None:
    settings = get_settings()
    get_qdrant_client().delete(
        collection_name=settings.qdrant_chunks_collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key='file_id',
                        match=models.MatchValue(value=file_id),
                    )
                ]
            )
        ),
        wait=True,
    )


def upsert_points(points: list[models.PointStruct]) -> None:
    if not points:
        return
    settings = get_settings()
    get_qdrant_client().upsert(
        collection_name=settings.qdrant_chunks_collection,
        points=points,
        wait=True,
    )
