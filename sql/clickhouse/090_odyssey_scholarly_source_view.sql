CREATE VIEW IF NOT EXISTS odyssey_scholarly_source_v AS
SELECT
    scholarly_source_id,
    source_type,
    title,
    creator_names,
    publication_year,
    publisher,
    doi,
    url,
    license_id,
    citation_text,
    metadata
FROM scholarly_sources FINAL
WHERE review_status IN ('reviewed', 'trusted');
