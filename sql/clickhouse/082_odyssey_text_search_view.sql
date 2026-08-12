CREATE VIEW IF NOT EXISTS odyssey_text_search_v AS
SELECT
    text_unit_id,
    version_id,
    book,
    line_start,
    line_end,
    citation,
    cts_urn,
    original_text,
    normalized_text,
    lowerUTF8(normalized_text) AS casefolded_text
FROM text_units FINAL
WHERE work_id = 'odyssey';
