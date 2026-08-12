CREATE TABLE IF NOT EXISTS theme_passages
(
    theme_passage_id String, theme_id String, text_unit_id String, rationale String,
    evidence_class LowCardinality(String), review_status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (theme_id, text_unit_id, theme_passage_id);
