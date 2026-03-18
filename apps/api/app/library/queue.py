import json

import redis


_client: redis.Redis | None = None


def init_redis_client(redis_url: str) -> None:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(redis_url, decode_responses=True)


def get_redis_client() -> redis.Redis:
    if _client is None:
        raise RuntimeError('Redis client has not been initialized.')
    return _client


def close_redis_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def enqueue_json(queue_name: str, payload: dict) -> int:
    return int(get_redis_client().rpush(queue_name, json.dumps(payload)))


def queue_length(queue_name: str) -> int:
    return int(get_redis_client().llen(queue_name))


def cache_get_json(key: str):
    raw = get_redis_client().get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def cache_set_json(key: str, payload, ttl_seconds: int | None = None) -> None:
    serialized = json.dumps(payload, default=str)
    client = get_redis_client()
    if ttl_seconds and ttl_seconds > 0:
        client.setex(key, ttl_seconds, serialized)
    else:
        client.set(key, serialized)


def cache_delete(key: str) -> None:
    get_redis_client().delete(key)
