import json

import redis

from app.config.settings import get_settings


_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def pop_job(queue_name: str, timeout_seconds: int) -> dict | None:
    result = get_client().blpop(queue_name, timeout=timeout_seconds)
    if not result:
        return None
    _, payload = result
    return json.loads(payload)
