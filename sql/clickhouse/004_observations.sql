CREATE TABLE IF NOT EXISTS observations
(
    observation_id String,
    extraction_run_id String,
    passage_id String,
    entry_id String,
    source_id String,
    category LowCardinality(String),
    canonical_term String,
    normalized_description String,
    explicit Bool,
    source_quote String,
    source_start UInt32,
    source_end UInt32,
    passage_sha256 FixedString(64),
    confidence Float32,
    model LowCardinality(String),
    schema_version LowCardinality(String),
    prompt_version LowCardinality(String),
    trusted Bool DEFAULT false,
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (passage_id, category, canonical_term, observation_id);
