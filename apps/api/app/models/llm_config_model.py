from uuid import UUID

from app.library.db import execute, execute_returning, fetch_all, fetch_one, scalar, to_jsonb


LIST_LLM_CONFIGS = """
SELECT
    id,
    name,
    provider,
    base_url,
    api_key,
    model,
    timeout_seconds,
    max_output_tokens,
    temperature,
    top_p,
    reasoning_effort,
    is_active,
    is_enabled,
    metadata,
    created_by,
    updated_by,
    created_at,
    updated_at
FROM llm_configs
ORDER BY is_active DESC, updated_at DESC, created_at DESC;
"""

GET_LLM_CONFIG = """
SELECT
    id,
    name,
    provider,
    base_url,
    api_key,
    model,
    timeout_seconds,
    max_output_tokens,
    temperature,
    top_p,
    reasoning_effort,
    is_active,
    is_enabled,
    metadata,
    created_by,
    updated_by,
    created_at,
    updated_at
FROM llm_configs
WHERE id = %s;
"""

GET_ACTIVE_LLM_CONFIG = """
SELECT
    id,
    name,
    provider,
    base_url,
    api_key,
    model,
    timeout_seconds,
    max_output_tokens,
    temperature,
    top_p,
    reasoning_effort,
    is_active,
    is_enabled,
    metadata,
    created_by,
    updated_by,
    created_at,
    updated_at
FROM llm_configs
WHERE is_active = TRUE
LIMIT 1;
"""

COUNT_LLM_CONFIGS = "SELECT COUNT(*) AS count FROM llm_configs;"

INSERT_LLM_CONFIG = """
INSERT INTO llm_configs (
    name,
    provider,
    base_url,
    api_key,
    model,
    timeout_seconds,
    max_output_tokens,
    temperature,
    top_p,
    reasoning_effort,
    is_active,
    is_enabled,
    metadata,
    created_by,
    updated_by
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id, name, provider, base_url, api_key, model, timeout_seconds, max_output_tokens, temperature, top_p, reasoning_effort, is_active, is_enabled, metadata, created_by, updated_by, created_at, updated_at;
"""

UPDATE_LLM_CONFIG = """
UPDATE llm_configs
SET
    name = %s,
    provider = %s,
    base_url = %s,
    api_key = %s,
    model = %s,
    timeout_seconds = %s,
    max_output_tokens = %s,
    temperature = %s,
    top_p = %s,
    reasoning_effort = %s,
    is_enabled = %s,
    metadata = %s,
    updated_by = %s,
    updated_at = NOW()
WHERE id = %s
RETURNING id, name, provider, base_url, api_key, model, timeout_seconds, max_output_tokens, temperature, top_p, reasoning_effort, is_active, is_enabled, metadata, created_by, updated_by, created_at, updated_at;
"""

DEACTIVATE_ALL_LLM_CONFIGS = "UPDATE llm_configs SET is_active = FALSE, updated_by = %s, updated_at = NOW() WHERE is_active = TRUE;"
ACTIVATE_LLM_CONFIG = "UPDATE llm_configs SET is_active = TRUE, updated_by = %s, updated_at = NOW() WHERE id = %s RETURNING id, name, provider, base_url, api_key, model, timeout_seconds, max_output_tokens, temperature, top_p, reasoning_effort, is_active, is_enabled, metadata, created_by, updated_by, created_at, updated_at;"
DELETE_LLM_CONFIG = "DELETE FROM llm_configs WHERE id = %s;"



def list_llm_configs(conn=None) -> list[dict]:
    return fetch_all(LIST_LLM_CONFIGS, conn=conn)



def get_llm_config(config_id: UUID | str, conn=None) -> dict | None:
    return fetch_one(GET_LLM_CONFIG, (str(config_id),), conn=conn)



def get_active_llm_config(conn=None) -> dict | None:
    return fetch_one(GET_ACTIVE_LLM_CONFIG, conn=conn)



def count_llm_configs(conn=None) -> int:
    return int(scalar(COUNT_LLM_CONFIGS, conn=conn) or 0)



def create_llm_config(*, name: str, provider: str, base_url: str | None, api_key: str | None, model: str, timeout_seconds: int, max_output_tokens: int, temperature: float, top_p: float, reasoning_effort: str | None, is_active: bool, is_enabled: bool, metadata: dict | None, created_by: UUID | None, updated_by: UUID | None, conn=None) -> dict | None:
    return execute_returning(
        INSERT_LLM_CONFIG,
        (
            name,
            provider,
            base_url,
            api_key,
            model,
            timeout_seconds,
            max_output_tokens,
            temperature,
            top_p,
            reasoning_effort,
            is_active,
            is_enabled,
            to_jsonb(metadata),
            str(created_by) if created_by else None,
            str(updated_by) if updated_by else None,
        ),
        conn=conn,
    )



def update_llm_config(*, config_id: UUID | str, name: str, provider: str, base_url: str | None, api_key: str | None, model: str, timeout_seconds: int, max_output_tokens: int, temperature: float, top_p: float, reasoning_effort: str | None, is_enabled: bool, metadata: dict | None, updated_by: UUID | None, conn=None) -> dict | None:
    return execute_returning(
        UPDATE_LLM_CONFIG,
        (
            name,
            provider,
            base_url,
            api_key,
            model,
            timeout_seconds,
            max_output_tokens,
            temperature,
            top_p,
            reasoning_effort,
            is_enabled,
            to_jsonb(metadata),
            str(updated_by) if updated_by else None,
            str(config_id),
        ),
        conn=conn,
    )



def deactivate_all_llm_configs(updated_by: UUID | None, conn=None) -> None:
    execute(DEACTIVATE_ALL_LLM_CONFIGS, (str(updated_by) if updated_by else None,), conn=conn)



def activate_llm_config(config_id: UUID | str, updated_by: UUID | None, conn=None) -> dict | None:
    return execute_returning(ACTIVATE_LLM_CONFIG, (str(updated_by) if updated_by else None, str(config_id)), conn=conn)



def delete_llm_config(config_id: UUID | str, conn=None) -> None:
    execute(DELETE_LLM_CONFIG, (str(config_id),), conn=conn)
