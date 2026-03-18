from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.settings import get_settings
from app.library.db import close_db_pool, init_db_pool
from app.library.qdrant import close_qdrant_client, init_qdrant_client
from app.library.queue import close_redis_client, init_redis_client
from app.library.storage import close_storage_client, init_storage_client
from app.routes import get_routers
from app.services.llm_service import close_llm_client, init_llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db_pool(settings.database_url)
    init_redis_client(settings.redis_url)
    init_storage_client(settings)
    init_qdrant_client(settings)
    init_llm_client(settings)
    try:
        yield
    finally:
        close_storage_client()
        close_qdrant_client()
        close_llm_client()
        close_redis_client()
        close_db_pool()


app = FastAPI(title='AI Stack API', version='0.4.0', lifespan=lifespan)

for router in get_routers():
    app.include_router(router)
