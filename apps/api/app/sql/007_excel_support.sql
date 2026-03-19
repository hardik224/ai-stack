ALTER TABLE files
    DROP CONSTRAINT IF EXISTS files_source_type_check;

ALTER TABLE files
    ADD CONSTRAINT files_source_type_check
    CHECK (source_type IN ('pdf', 'csv', 'excel'));

ALTER TABLE chunks
    DROP CONSTRAINT IF EXISTS chunks_source_type_check;

ALTER TABLE chunks
    ADD CONSTRAINT chunks_source_type_check
    CHECK (source_type IN ('pdf', 'csv', 'excel'));

UPDATE files
SET source_type = 'excel'
WHERE LOWER(original_name) LIKE '%.xlsx'
   OR LOWER(original_name) LIKE '%.xls'
   OR content_type IN (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'application/excel',
        'application/x-excel',
        'application/x-msexcel'
   );

UPDATE chunks AS c
SET source_type = 'excel'
FROM files AS f
WHERE f.id = c.file_id
  AND f.source_type = 'excel';
