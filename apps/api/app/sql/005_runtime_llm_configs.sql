CREATE TABLE IF NOT EXISTS llm_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(64) NOT NULL CHECK (provider IN ('anthropic', 'openai', 'openai_compatible')),
    base_url TEXT NULL,
    api_key TEXT NULL,
    model VARCHAR(255) NOT NULL,
    timeout_seconds INTEGER NOT NULL DEFAULT 180 CHECK (timeout_seconds > 0),
    max_output_tokens INTEGER NOT NULL DEFAULT 1400 CHECK (max_output_tokens > 0),
    temperature NUMERIC(4, 2) NOT NULL DEFAULT 0.60 CHECK (temperature >= 0 AND temperature <= 2),
    top_p NUMERIC(4, 2) NOT NULL DEFAULT 0.95 CHECK (top_p >= 0 AND top_p <= 1),
    reasoning_effort VARCHAR(32) NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS llm_configs_name_unique_idx ON llm_configs (LOWER(name));
CREATE UNIQUE INDEX IF NOT EXISTS llm_configs_single_active_idx ON llm_configs ((is_active)) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS llm_configs_provider_idx ON llm_configs (provider);
CREATE INDEX IF NOT EXISTS llm_configs_enabled_idx ON llm_configs (is_enabled);

DROP TRIGGER IF EXISTS llm_configs_set_updated_at ON llm_configs;
CREATE TRIGGER llm_configs_set_updated_at BEFORE UPDATE ON llm_configs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
