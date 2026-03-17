import os
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_host: str
    api_port: int
    database_url: str
    redis_url: str
    qdrant_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool
    minio_documents_bucket: str
    auth_session_ttl_hours: int
    ingestion_queue_name: str
    max_upload_size_bytes: int
    default_list_limit: int
    max_list_limit: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "2000")),
        database_url=os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6380/0"),
        qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "")),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", "")),
        minio_secure=_as_bool(os.getenv("MINIO_SECURE"), default=False),
        minio_documents_bucket=os.getenv("MINIO_DOCUMENTS_BUCKET", "documents"),
        auth_session_ttl_hours=int(os.getenv("AUTH_SESSION_TTL_HOURS", "168")),
        ingestion_queue_name=os.getenv("INGESTION_QUEUE_NAME", "ai_stack:ingestion_jobs"),
        max_upload_size_bytes=int(os.getenv("MAX_UPLOAD_SIZE_BYTES", "52428800")),
        default_list_limit=int(os.getenv("DEFAULT_LIST_LIMIT", "50")),
        max_list_limit=int(os.getenv("MAX_LIST_LIMIT", "100")),
    )
