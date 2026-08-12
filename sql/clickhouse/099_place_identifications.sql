CREATE TABLE IF NOT EXISTS place_identifications
(
    identification_id String, poetic_place_id String, ancient_place_id Nullable(String),
    hypothesis_id String, identification_class LowCardinality(String),
    longitude Nullable(Float64), latitude Nullable(Float64), confidence LowCardinality(String),
    status LowCardinality(String), rationale String, scholarly_source_ids Array(String),
    review_status LowCardinality(String), release_id String, record_sha256 FixedString(64),
    updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (hypothesis_id, poetic_place_id, identification_id);
