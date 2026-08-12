CREATE VIEW IF NOT EXISTS odyssey_text_lookup_v AS
SELECT
    text_unit_id,
    work_id,
    version_id,
    book,
    line_start,
    line_end,
    citation,
    cts_urn,
    unit_index,
    original_text,
    normalized_text,
    text_sha256
FROM text_units FINAL
WHERE work_id = 'odyssey';
