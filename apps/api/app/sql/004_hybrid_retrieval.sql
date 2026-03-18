CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS chunks_content_fts_english_idx
    ON chunks USING GIN (to_tsvector('english', COALESCE(content, '')));

CREATE INDEX IF NOT EXISTS chunks_content_fts_simple_idx
    ON chunks USING GIN (to_tsvector('simple', COALESCE(content, '')));

CREATE INDEX IF NOT EXISTS files_original_name_trgm_idx
    ON files USING GIN (original_name gin_trgm_ops);
