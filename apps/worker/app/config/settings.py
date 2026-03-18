import os
import socket
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class Settings:
    app_env: str
    redis_url: str
    database_url: str
    ingestion_queue_name: str
    worker_id: str
    block_timeout_seconds: int
    simulation_delay_seconds: float
    qdrant_url: str
    qdrant_timeout_seconds: int
    qdrant_chunks_collection: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool
    minio_documents_bucket: str
    embedding_model_name: str
    embedding_batch_size: int
    indexing_batch_size: int
    chunk_size_chars: int
    chunk_overlap_chars: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv('APP_ENV', 'development'),
        redis_url=os.getenv('REDIS_URL', 'redis://redis:6380/0'),
        database_url=os.getenv('DATABASE_URL', ''),
        ingestion_queue_name=os.getenv('INGESTION_QUEUE_NAME', 'ai_stack:ingestion_jobs'),
        worker_id=os.getenv('WORKER_ID', socket.gethostname()),
        block_timeout_seconds=int(os.getenv('WORKER_BLOCK_TIMEOUT_SECONDS', '5')),
        simulation_delay_seconds=float(os.getenv('WORKER_SIMULATION_DELAY_SECONDS', '0')),
        qdrant_url=os.getenv('QDRANT_URL', 'http://qdrant:6333'),
        qdrant_timeout_seconds=int(os.getenv('QDRANT_TIMEOUT_SECONDS', '30')),
        qdrant_chunks_collection=os.getenv('QDRANT_CHUNKS_COLLECTION', 'ai_stack_chunks'),
        minio_endpoint=os.getenv('MINIO_ENDPOINT', 'http://minio:9000'),
        minio_access_key=os.getenv('MINIO_ACCESS_KEY', os.getenv('MINIO_ROOT_USER', '')),
        minio_secret_key=os.getenv('MINIO_SECRET_KEY', os.getenv('MINIO_ROOT_PASSWORD', '')),
        minio_secure=_as_bool(os.getenv('MINIO_SECURE'), default=False),
        minio_documents_bucket=os.getenv('MINIO_DOCUMENTS_BUCKET', 'documents'),
        embedding_model_name=os.getenv('EMBEDDING_MODEL_NAME', 'BAAI/bge-small-en-v1.5'),
        embedding_batch_size=int(os.getenv('EMBEDDING_BATCH_SIZE', '64')),
        indexing_batch_size=int(os.getenv('INDEXING_BATCH_SIZE', '64')),
        chunk_size_chars=int(os.getenv('CHUNK_SIZE_CHARS', '1200')),
        chunk_overlap_chars=int(os.getenv('CHUNK_OVERLAP_CHARS', '150')),
    )
