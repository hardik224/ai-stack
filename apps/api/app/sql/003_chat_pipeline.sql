ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS error_message TEXT NULL,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chat_messages_status_check'
    ) THEN
        ALTER TABLE chat_messages
            ADD CONSTRAINT chat_messages_status_check
            CHECK (status IN ('streaming', 'completed', 'failed'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS chat_messages_status_created_at_idx ON chat_messages (status, created_at DESC);
CREATE INDEX IF NOT EXISTS chat_sessions_user_updated_at_idx ON chat_sessions (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_message_sources (
    id BIGSERIAL PRIMARY KEY,
    message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    citation_label VARCHAR(16) NOT NULL,
    rank INTEGER NOT NULL CHECK (rank >= 1),
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_message_sources_message_id_idx ON chat_message_sources (message_id, rank);
CREATE INDEX IF NOT EXISTS chat_message_sources_chunk_id_idx ON chat_message_sources (chunk_id);
CREATE INDEX IF NOT EXISTS chat_message_sources_file_id_idx ON chat_message_sources (file_id);

CREATE TABLE IF NOT EXISTS retrieval_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NULL REFERENCES chat_sessions(id) ON DELETE SET NULL,
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    assistant_message_id UUID NULL REFERENCES chat_messages(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    normalized_query TEXT NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    top_k INTEGER NOT NULL CHECK (top_k >= 1),
    score_threshold DOUBLE PRECISION NULL,
    dedupe_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    hit_count INTEGER NOT NULL DEFAULT 0 CHECK (hit_count >= 0),
    timings JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS retrieval_logs_session_created_at_idx ON retrieval_logs (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS retrieval_logs_user_created_at_idx ON retrieval_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS retrieval_logs_assistant_message_idx ON retrieval_logs (assistant_message_id);

DROP TRIGGER IF EXISTS chat_messages_set_updated_at ON chat_messages;
CREATE TRIGGER chat_messages_set_updated_at BEFORE UPDATE ON chat_messages
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
