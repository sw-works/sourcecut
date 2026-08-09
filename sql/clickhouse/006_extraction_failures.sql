CREATE TABLE IF NOT EXISTS extraction_failures
(
    failure_id String,
    run_id String,
    passage_id String,
    failure_type LowCardinality(String),
    retryable Bool,
    attempt UInt8,
    error_message String,
    raw_response String DEFAULT '',
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (passage_id, created_at, failure_id);
