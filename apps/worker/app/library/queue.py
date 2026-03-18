import json

from app.library.redis_client import get_redis_client



def pop_job(queue_name: str, timeout_seconds: int) -> dict | None:
    result = get_redis_client().blpop(queue_name, timeout=timeout_seconds)
    if not result:
        return None
    _, payload = result
    return json.loads(payload)
