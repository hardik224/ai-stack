ALTER TABLE files
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(16),
    ADD COLUMN IF NOT EXISTS page_count INTEGER NULL CHECK (page_count IS NULL OR page_count >= 0),
    ADD COLUMN IF NOT EXISTS row_count INTEGER NULL CHECK (row_count IS NULL OR row_count >= 0),
    ADD COLUMN IF NOT EXISTS total_chunks INTEGER NOT NULL DEFAULT 0 CHECK (total_chunks >= 0),
    ADD COLUMN IF NOT EXISTS indexed_chunks INTEGER NOT NULL DEFAULT 0 CHECK (indexed_chunks >= 0),
    ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
    ADD COLUMN IF NOT EXISTS last_ingested_job_id UUID NULL,
    ADD COLUMN IF NOT EXISTS last_ingested_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS error_message TEXT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'files_source_type_check'
    ) THEN
        ALTER TABLE files
            ADD CONSTRAINT files_source_type_check
            CHECK (source_type IN ('pdf', 'csv'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'files_ingestion_status_check'
    ) THEN
        ALTER TABLE files
            ADD CONSTRAINT files_ingestion_status_check
            CHECK (ingestion_status IN ('uploaded', 'queued', 'downloading', 'parsing', 'chunking', 'embedding', 'indexing', 'completed', 'failed'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'files_last_ingested_job_fk'
    ) THEN
        ALTER TABLE files
            ADD CONSTRAINT files_last_ingested_job_fk
            FOREIGN KEY (last_ingested_job_id) REFERENCES ingestion_jobs(id) ON DELETE SET NULL;
    END IF;
END $$;

UPDATE files
SET source_type = CASE
    WHEN source_type IS NOT NULL THEN source_type
    WHEN content_type = 'application/pdf' OR LOWER(original_name) LIKE '%.pdf' THEN 'pdf'
    WHEN content_type IN ('text/csv', 'application/csv') OR LOWER(original_name) LIKE '%.csv' THEN 'csv'
    ELSE 'pdf'
END
WHERE source_type IS NULL;

ALTER TABLE files
    ALTER COLUMN source_type SET NOT NULL;

CREATE INDEX IF NOT EXISTS files_source_type_idx ON files (source_type);
CREATE INDEX IF NOT EXISTS files_ingestion_status_idx ON files (ingestion_status);
CREATE INDEX IF NOT EXISTS files_last_ingested_job_id_idx ON files (last_ingested_job_id);

ALTER TABLE ingestion_jobs
    ADD COLUMN IF NOT EXISTS total_chunks INTEGER NOT NULL DEFAULT 0 CHECK (total_chunks >= 0),
    ADD COLUMN IF NOT EXISTS processed_chunks INTEGER NOT NULL DEFAULT 0 CHECK (processed_chunks >= 0),
    ADD COLUMN IF NOT EXISTS indexed_chunks INTEGER NOT NULL DEFAULT 0 CHECK (indexed_chunks >= 0),
    ADD COLUMN IF NOT EXISTS progress_message TEXT NULL;

CREATE INDEX IF NOT EXISTS ingestion_jobs_file_stage_idx ON ingestion_jobs (file_id, current_stage);

ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS collection_id UUID NULL,
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(16) NULL,
    ADD COLUMN IF NOT EXISTS page_number INTEGER NULL CHECK (page_number IS NULL OR page_number >= 1),
    ADD COLUMN IF NOT EXISTS row_number INTEGER NULL CHECK (row_number IS NULL OR row_number >= 1),
    ADD COLUMN IF NOT EXISTS content_hash CHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS qdrant_point_id UUID NULL,
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS indexed_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chunks_collection_id_fk'
    ) THEN
        ALTER TABLE chunks
            ADD CONSTRAINT chunks_collection_id_fk
            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chunks_source_type_check'
    ) THEN
        ALTER TABLE chunks
            ADD CONSTRAINT chunks_source_type_check
            CHECK (source_type IN ('pdf', 'csv'));
    END IF;
END $$;

UPDATE chunks AS c
SET
    collection_id = f.collection_id,
    source_type = COALESCE(c.source_type, f.source_type)
FROM files AS f
WHERE f.id = c.file_id
  AND (c.collection_id IS NULL OR c.source_type IS NULL);

ALTER TABLE chunks
    ALTER COLUMN collection_id SET NOT NULL,
    ALTER COLUMN source_type SET NOT NULL;

CREATE INDEX IF NOT EXISTS chunks_collection_id_idx ON chunks (collection_id);
CREATE INDEX IF NOT EXISTS chunks_source_type_idx ON chunks (source_type);
CREATE INDEX IF NOT EXISTS chunks_file_position_idx ON chunks (file_id, chunk_index);
CREATE INDEX IF NOT EXISTS chunks_file_page_number_idx ON chunks (file_id, page_number) WHERE page_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS chunks_file_row_number_idx ON chunks (file_id, row_number) WHERE row_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS chunks_qdrant_point_id_uidx ON chunks (qdrant_point_id) WHERE qdrant_point_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS chunks_content_hash_idx ON chunks (content_hash);
