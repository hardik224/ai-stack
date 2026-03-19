import hashlib
import json
import time
from uuid import UUID

from app.config.settings import get_settings
from app.library.redis_client import get_redis_client


CACHE_NAMESPACE = 'ai-stack'
EMBED_VERSION = 'v1'
RETRIEVAL_VERSION = 'v2'
PROMPT_VERSION = 'v1'
ANSWER_VERSION = 'v1'
GLOBAL_VERSION_KEY = f'{CACHE_NAMESPACE}:cache_version:global'
COLLECTION_VERSION_PREFIX = f'{CACHE_NAMESPACE}:cache_version:collection'
LLM_CONFIG_VERSION_KEY = f'{CACHE_NAMESPACE}:llm_config:version'



def build_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode('utf-8')).hexdigest()



def make_key(prefix: str, *, version: str | None = None, signature=None) -> str:
    digest = build_hash(signature if signature is not None else prefix)
    if version:
        return f'{CACHE_NAMESPACE}:{prefix}:{version}:{digest}'
    return f'{CACHE_NAMESPACE}:{prefix}:{digest}'



def get_json(key: str):
    raw = get_redis_client().get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None



def set_json(key: str, payload, ttl_seconds: int | None = None) -> None:
    serialized = json.dumps(payload, default=str)
    client = get_redis_client()
    if ttl_seconds and ttl_seconds > 0:
        client.setex(key, ttl_seconds, serialized)
    else:
        client.set(key, serialized)



def get_int(key: str, default: int = 1) -> int:
    raw = get_redis_client().get(key)
    if raw is None:
        get_redis_client().setnx(key, str(default))
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default



def incr(key: str) -> int:
    client = get_redis_client()
    client.setnx(key, '1')
    return int(client.incr(key))



def get_ttl(key: str) -> int | None:
    ttl = int(get_redis_client().ttl(key))
    if ttl < 0:
        return None
    return ttl



def get_global_cache_version() -> int:
    return get_int(GLOBAL_VERSION_KEY, default=1)



def get_collection_cache_version(collection_id: UUID | str | None) -> int:
    if not collection_id:
        return get_global_cache_version()
    key = f'{COLLECTION_VERSION_PREFIX}:{collection_id}'
    return get_int(key, default=1)



def get_llm_config_version() -> int:
    return get_int(LLM_CONFIG_VERSION_KEY, default=1)



def get_retrieval_cache_scope(*, collection_id: UUID | str | None = None, fallback_scope: str = 'global') -> dict:
    if collection_id:
        return {
            'scope': 'collection',
            'scope_id': str(collection_id),
            'version': get_collection_cache_version(collection_id),
        }
    return {
        'scope': fallback_scope,
        'scope_id': None,
        'version': get_global_cache_version(),
    }



def build_embedding_cache_key(*, normalized_query: str, model_name: str) -> str:
    return make_key(
        'embedding',
        version=EMBED_VERSION,
        signature={'model_name': model_name, 'normalized_query': normalized_query},
    )



def build_retrieval_cache_key(*, signature: dict, version_scope: dict) -> str:
    return make_key(
        'retrieval',
        version=f"{RETRIEVAL_VERSION}:{version_scope['scope']}:{version_scope['version']}",
        signature=signature,
    )



def build_prompt_cache_key(*, signature: dict, version_scope: dict) -> str:
    return make_key(
        'prompt',
        version=f"{PROMPT_VERSION}:{version_scope['scope']}:{version_scope['version']}",
        signature=signature,
    )



def build_answer_cache_key(*, signature: dict, version_scope: dict) -> str:
    return make_key(
        'answer',
        version=f"{ANSWER_VERSION}:{version_scope['scope']}:{version_scope['version']}",
        signature=signature,
    )



def get_cached_embedding(*, normalized_query: str, model_name: str):
    key = build_embedding_cache_key(normalized_query=normalized_query, model_name=model_name)
    started = time.perf_counter()
    payload = get_json(key)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return payload, {'hit': payload is not None, 'key': key, 'lookup_ms': elapsed}



def set_cached_embedding(*, normalized_query: str, model_name: str, vector: list[float]) -> None:
    settings = get_settings()
    key = build_embedding_cache_key(normalized_query=normalized_query, model_name=model_name)
    set_json(key, vector, settings.cache_embedding_ttl_seconds)



def get_cached_retrieval(*, signature: dict, version_scope: dict):
    key = build_retrieval_cache_key(signature=signature, version_scope=version_scope)
    started = time.perf_counter()
    payload = get_json(key)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return payload, {'hit': payload is not None, 'key': key, 'lookup_ms': elapsed, 'version_scope': version_scope}



def set_cached_retrieval(*, signature: dict, version_scope: dict, payload: dict) -> None:
    settings = get_settings()
    key = build_retrieval_cache_key(signature=signature, version_scope=version_scope)
    set_json(key, payload, settings.cache_retrieval_ttl_seconds)



def get_cached_prompt(*, signature: dict, version_scope: dict):
    key = build_prompt_cache_key(signature=signature, version_scope=version_scope)
    started = time.perf_counter()
    payload = get_json(key)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return payload, {'hit': payload is not None, 'key': key, 'lookup_ms': elapsed}



def set_cached_prompt(*, signature: dict, version_scope: dict, payload: list[dict]) -> None:
    settings = get_settings()
    if not settings.cache_prompt_enabled:
        return
    key = build_prompt_cache_key(signature=signature, version_scope=version_scope)
    set_json(key, payload, settings.cache_prompt_ttl_seconds)



def get_cached_answer(*, signature: dict, version_scope: dict):
    key = build_answer_cache_key(signature=signature, version_scope=version_scope)
    started = time.perf_counter()
    payload = get_json(key)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return payload, {'hit': payload is not None, 'key': key, 'lookup_ms': elapsed}



def set_cached_answer(*, signature: dict, version_scope: dict, payload: dict) -> None:
    settings = get_settings()
    if not settings.cache_answer_enabled:
        return
    key = build_answer_cache_key(signature=signature, version_scope=version_scope)
    set_json(key, payload, settings.cache_answer_ttl_seconds)
