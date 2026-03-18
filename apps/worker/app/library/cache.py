from uuid import UUID

from app.library.redis_client import get_redis_client


CACHE_NAMESPACE = 'ai-stack'
GLOBAL_VERSION_KEY = f'{CACHE_NAMESPACE}:cache_version:global'
COLLECTION_VERSION_PREFIX = f'{CACHE_NAMESPACE}:cache_version:collection'



def bump_retrieval_cache_versions(*, collection_id: UUID | str | None) -> dict:
    client = get_redis_client()
    client.setnx(GLOBAL_VERSION_KEY, '1')
    global_version = int(client.incr(GLOBAL_VERSION_KEY))
    collection_version = None
    if collection_id:
        collection_key = f'{COLLECTION_VERSION_PREFIX}:{collection_id}'
        client.setnx(collection_key, '1')
        collection_version = int(client.incr(collection_key))
    return {
        'global_version': global_version,
        'collection_version': collection_version,
    }
