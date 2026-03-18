import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.settings import get_settings
from app.library.db import close_db_pool, init_db_pool
from app.library.qdrant import close_qdrant_client, init_qdrant_client
from app.library.queue import close_redis_client, init_redis_client
from app.library.storage import close_storage_client, ensure_bucket_exists, init_storage_client
from app.middleware.request_context import RequestContextMiddleware
from app.routes import get_routers


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    init_db_pool(settings.database_url)
    init_redis_client(settings.redis_url)
    init_storage_client(settings)
    init_qdrant_client(settings)

    try:
        ensure_bucket_exists(settings.minio_documents_bucket)
    except Exception as exc:  # pragma: no cover - defensive startup logging
        logger.warning('MinIO bucket bootstrap failed: %s', exc)

    yield

    close_qdrant_client()
    close_storage_client()
    close_redis_client()
    close_db_pool()


app = FastAPI(title='AI Stack API', version='0.3.0', lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)

for router in get_routers():
    app.include_router(router)
