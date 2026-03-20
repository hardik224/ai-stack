ALTER TABLE files
    DROP CONSTRAINT IF EXISTS files_source_type_check;

ALTER TABLE files
    ADD CONSTRAINT files_source_type_check
    CHECK (source_type IN ('pdf', 'csv', 'excel', 'txt'));

ALTER TABLE chunks
    DROP CONSTRAINT IF EXISTS chunks_source_type_check;

ALTER TABLE chunks
    ADD CONSTRAINT chunks_source_type_check
    CHECK (source_type IN ('pdf', 'csv', 'excel', 'txt'));

UPDATE files
SET source_type = 'txt'
WHERE LOWER(original_name) LIKE '%.txt'
   OR content_type = 'text/plain';

UPDATE chunks AS c
SET source_type = 'txt'
FROM files AS f
WHERE f.id = c.file_id
  AND f.source_type = 'txt';
