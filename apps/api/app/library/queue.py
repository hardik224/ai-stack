import json

from app.library.redis_client import get_redis_client



def enqueue_json(queue_name: str, payload: dict) -> int:
    return int(get_redis_client().rpush(queue_name, json.dumps(payload)))



def queue_length(queue_name: str) -> int:
    return int(get_redis_client().llen(queue_name))
