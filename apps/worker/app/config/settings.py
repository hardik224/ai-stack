import os
import socket
from dataclasses import dataclass
from functools import lru_cache


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
    minio_endpoint: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6380/0"),
        database_url=os.getenv("DATABASE_URL", ""),
        ingestion_queue_name=os.getenv("INGESTION_QUEUE_NAME", "ai_stack:ingestion_jobs"),
        worker_id=os.getenv("WORKER_ID", socket.gethostname()),
        block_timeout_seconds=int(os.getenv("WORKER_BLOCK_TIMEOUT_SECONDS", "5")),
        simulation_delay_seconds=float(os.getenv("WORKER_SIMULATION_DELAY_SECONDS", "1")),
        qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
    )
