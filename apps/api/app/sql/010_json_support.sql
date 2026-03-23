ALTER TABLE files
    DROP CONSTRAINT IF EXISTS files_source_type_check;

ALTER TABLE files
    ADD CONSTRAINT files_source_type_check
    CHECK (source_type IN ('pdf', 'csv', 'excel', 'txt', 'json'));

ALTER TABLE chunks
    DROP CONSTRAINT IF EXISTS chunks_source_type_check;

ALTER TABLE chunks
    ADD CONSTRAINT chunks_source_type_check
    CHECK (source_type IN ('pdf', 'csv', 'excel', 'txt', 'json'));

UPDATE files
SET source_type = 'json'
WHERE LOWER(original_name) LIKE '%.json'
   OR content_type IN ('application/json', 'text/json');

UPDATE chunks AS c
SET source_type = 'json'
FROM files AS f
WHERE f.id = c.file_id
  AND f.source_type = 'json';
