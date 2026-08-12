CREATE TABLE IF NOT EXISTS route_hypotheses
(
    hypothesis_id String, title String, author_or_tradition String, description String,
    scholarly_source_ids Array(String), license_id String, display_order UInt16,
    is_default Bool, review_status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (display_order, hypothesis_id);
