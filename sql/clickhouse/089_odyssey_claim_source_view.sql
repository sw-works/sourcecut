CREATE VIEW IF NOT EXISTS odyssey_claim_source_v AS
SELECT
    u.text_unit_id,
    u.version_id,
    u.book,
    u.line_start,
    u.line_end,
    u.citation,
    u.cts_urn,
    u.original_text,
    u.normalized_text,
    u.text_sha256,
    u.source_document_id,
    v.source_sha256 AS source_version_hash,
    v.source_url,
    v.bibliographic_description,
    v.display_decision
FROM text_units AS u FINAL
INNER JOIN source_versions AS v FINAL ON v.version_id = u.version_id
WHERE u.work_id = 'odyssey';
