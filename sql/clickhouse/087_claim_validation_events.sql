CREATE TABLE IF NOT EXISTS claim_validation_events
(
    validation_event_id String,
    claim_id String,
    claim_evidence_id String,
    validator_version LowCardinality(String),
    validation_status LowCardinality(String),
    validation_errors Array(String),
    source_snapshot_hash Nullable(FixedString(64)),
    occurred_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (claim_id, occurred_at, validation_event_id);
