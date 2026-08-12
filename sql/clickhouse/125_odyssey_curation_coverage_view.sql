CREATE VIEW IF NOT EXISTS odyssey_curation_coverage_v AS
SELECT
    target_type,
    status,
    uniqExact(record_id) AS record_count,
    max(updated_at) AS last_reviewed_at
FROM curation_records
GROUP BY target_type, status;
