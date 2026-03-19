ALTER TABLE llm_configs
DROP CONSTRAINT IF EXISTS llm_configs_provider_check;

ALTER TABLE llm_configs
ADD CONSTRAINT llm_configs_provider_check
CHECK (provider IN ('anthropic', 'openai', 'openai_compatible', 'gemini'));
