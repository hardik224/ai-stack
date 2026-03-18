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
