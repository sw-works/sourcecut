CREATE TABLE IF NOT EXISTS asset_relationship_assessments
(
    assessment_id String, asset_id String, relationship_class LowCardinality(String),
    production_use String, limitations String, evidence_ids Array(String), confidence LowCardinality(String),
    verification_status LowCardinality(String), review_status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (asset_id, assessment_id);
