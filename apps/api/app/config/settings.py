import os
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_host: str
    api_port: int
    database_url: str
    redis_url: str
    qdrant_url: str
    qdrant_timeout_seconds: int
    qdrant_chunks_collection: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool
    minio_documents_bucket: str
    auth_session_ttl_hours: int
    ingestion_queue_name: str
    max_upload_size_bytes: int
    default_list_limit: int
    max_list_limit: int
    embedding_model_name: str
    search_default_limit: int
    search_max_limit: int
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: int
    llm_max_output_tokens: int
    llm_temperature: float
    llm_top_p: float
    llm_reasoning_effort: str | None
    chat_default_mode: str
    chat_history_turns: int
    chat_retrieval_fetch_k: int
    chat_default_top_k: int
    chat_default_score_threshold: float
    chat_default_max_context_chunks: int
    chat_default_max_context_chars: int
    chat_retrieval_cache_ttl_seconds: int
    chat_embedding_cache_ttl_seconds: int
    chat_min_grounding_items: int
    chat_min_grounding_score: float
    chat_min_grounding_lexical_overlap: float
    hybrid_keyword_fetch_k: int
    hybrid_rrf_k: int
    hybrid_vector_weight: float
    hybrid_keyword_weight: float
    rerank_enabled: bool
    rerank_provider: str
    rerank_max_candidates: int
    sse_heartbeat_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    reasoning_effort = os.getenv('LLM_REASONING_EFFORT', '').strip() or None
    llm_provider = os.getenv('LLM_PROVIDER', os.getenv('LLM_BACKEND', 'openai_compatible')).strip() or 'openai_compatible'
    return Settings(
        app_env=os.getenv('APP_ENV', 'development'),
        api_host=os.getenv('API_HOST', '0.0.0.0'),
        api_port=int(os.getenv('API_PORT', '2000')),
        database_url=os.getenv('DATABASE_URL', ''),
        redis_url=os.getenv('REDIS_URL', 'redis://redis:6380/0'),
        qdrant_url=os.getenv('QDRANT_URL', 'http://qdrant:6333'),
        qdrant_timeout_seconds=int(os.getenv('QDRANT_TIMEOUT_SECONDS', '30')),
        qdrant_chunks_collection=os.getenv('QDRANT_CHUNKS_COLLECTION', 'ai_stack_chunks'),
        minio_endpoint=os.getenv('MINIO_ENDPOINT', 'http://minio:9000'),
        minio_access_key=os.getenv('MINIO_ACCESS_KEY', os.getenv('MINIO_ROOT_USER', '')),
        minio_secret_key=os.getenv('MINIO_SECRET_KEY', os.getenv('MINIO_ROOT_PASSWORD', '')),
        minio_secure=_as_bool(os.getenv('MINIO_SECURE'), default=False),
        minio_documents_bucket=os.getenv('MINIO_DOCUMENTS_BUCKET', 'documents'),
        auth_session_ttl_hours=int(os.getenv('AUTH_SESSION_TTL_HOURS', '168')),
        ingestion_queue_name=os.getenv('INGESTION_QUEUE_NAME', 'ai_stack:ingestion_jobs'),
        max_upload_size_bytes=int(os.getenv('MAX_UPLOAD_SIZE_BYTES', '52428800')),
        default_list_limit=int(os.getenv('DEFAULT_LIST_LIMIT', '50')),
        max_list_limit=int(os.getenv('MAX_LIST_LIMIT', '100')),
        embedding_model_name=os.getenv('EMBEDDING_MODEL_NAME', 'BAAI/bge-small-en-v1.5'),
        search_default_limit=int(os.getenv('SEARCH_DEFAULT_LIMIT', '5')),
        search_max_limit=int(os.getenv('SEARCH_MAX_LIMIT', '20')),
        llm_provider=llm_provider,
        llm_base_url=os.getenv('LLM_BASE_URL', ''),
        llm_api_key=os.getenv('LLM_API_KEY', 'local-vllm-key'),
        llm_model=os.getenv('LLM_MODEL', 'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B'),
        llm_timeout_seconds=int(os.getenv('LLM_TIMEOUT_SECONDS', '180')),
        llm_max_output_tokens=int(os.getenv('LLM_MAX_OUTPUT_TOKENS', '1400')),
        llm_temperature=float(os.getenv('LLM_TEMPERATURE', '0.6')),
        llm_top_p=float(os.getenv('LLM_TOP_P', '0.95')),
        llm_reasoning_effort=reasoning_effort,
        chat_default_mode=os.getenv('CHAT_DEFAULT_MODE', 'knowledge_qa'),
        chat_history_turns=int(os.getenv('CHAT_HISTORY_TURNS', '6')),
        chat_retrieval_fetch_k=int(os.getenv('CHAT_RETRIEVAL_FETCH_K', '12')),
        chat_default_top_k=int(os.getenv('CHAT_DEFAULT_TOP_K', '6')),
        chat_default_score_threshold=float(os.getenv('CHAT_DEFAULT_SCORE_THRESHOLD', '0.25')),
        chat_default_max_context_chunks=int(os.getenv('CHAT_DEFAULT_MAX_CONTEXT_CHUNKS', '6')),
        chat_default_max_context_chars=int(os.getenv('CHAT_DEFAULT_MAX_CONTEXT_CHARS', '12000')),
        chat_retrieval_cache_ttl_seconds=int(os.getenv('CHAT_RETRIEVAL_CACHE_TTL_SECONDS', '60')),
        chat_embedding_cache_ttl_seconds=int(os.getenv('CHAT_EMBEDDING_CACHE_TTL_SECONDS', '300')),
        chat_min_grounding_items=int(os.getenv('CHAT_MIN_GROUNDING_ITEMS', '1')),
        chat_min_grounding_score=float(os.getenv('CHAT_MIN_GROUNDING_SCORE', '0.38')),
        chat_min_grounding_lexical_overlap=float(os.getenv('CHAT_MIN_GROUNDING_LEXICAL_OVERLAP', '0.08')),
        hybrid_keyword_fetch_k=int(os.getenv('HYBRID_KEYWORD_FETCH_K', '12')),
        hybrid_rrf_k=int(os.getenv('HYBRID_RRF_K', '60')),
        hybrid_vector_weight=float(os.getenv('HYBRID_VECTOR_WEIGHT', '0.55')),
        hybrid_keyword_weight=float(os.getenv('HYBRID_KEYWORD_WEIGHT', '0.75')),
        rerank_enabled=_as_bool(os.getenv('RERANK_ENABLED'), default=True),
        rerank_provider=os.getenv('RERANK_PROVIDER', 'heuristic').strip() or 'heuristic',
        rerank_max_candidates=int(os.getenv('RERANK_MAX_CANDIDATES', '18')),
        sse_heartbeat_seconds=int(os.getenv('SSE_HEARTBEAT_SECONDS', '10')),
    )
