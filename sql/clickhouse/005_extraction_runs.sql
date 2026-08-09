CREATE TABLE IF NOT EXISTS extraction_runs
(
    run_id String,
    idempotency_key FixedString(64),
    passage_id String,
    passage_sha256 FixedString(64),
    model LowCardinality(String),
    schema_version LowCardinality(String),
    prompt_version LowCardinality(String),
    status LowCardinality(String),
    attempt UInt8,
    observations_inserted UInt16 DEFAULT 0,
    started_at DateTime64(3, 'UTC'),
    completed_at Nullable(DateTime64(3, 'UTC')),
    error_message String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (idempotency_key, started_at, run_id);
