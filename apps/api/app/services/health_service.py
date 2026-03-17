from fastapi import HTTPException, status

from app.config.settings import get_settings
from app.library.db import fetch_one
from app.library.queue import queue_length


def get_health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "api",
        "app_env": settings.app_env,
        "dependencies": {
            "database_configured": bool(settings.database_url),
            "redis_configured": bool(settings.redis_url),
            "minio_configured": bool(settings.minio_endpoint),
            "qdrant_configured": bool(settings.qdrant_url),
        },
    }


def get_db_health() -> dict:
    settings = get_settings()
    try:
        db_row = fetch_one("SELECT current_database() AS database_name, NOW() AS checked_at;")
        current_queue_depth = queue_length(settings.ingestion_queue_name)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "message": str(exc)},
        ) from exc

    return {
        "status": "ok",
        "database": db_row,
        "queue_depth": current_queue_depth,
    }
