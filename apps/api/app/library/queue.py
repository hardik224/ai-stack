import json

import redis


_client: redis.Redis | None = None


def init_redis_client(redis_url: str) -> None:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(redis_url, decode_responses=True)


def get_redis_client() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis client has not been initialized.")
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
