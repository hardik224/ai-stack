import redis

from app.config.settings import get_settings


_client: redis.Redis | None = None



def init_redis_client(redis_url: str | None = None) -> None:
    global _client
    if _client is None:
        resolved_url = redis_url or get_settings().redis_url
        _client = redis.Redis.from_url(resolved_url, decode_responses=True)



def get_redis_client() -> redis.Redis:
    global _client
    if _client is None:
        init_redis_client()
    if _client is None:
        raise RuntimeError('Redis client has not been initialized.')
    return _client



def close_redis_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
