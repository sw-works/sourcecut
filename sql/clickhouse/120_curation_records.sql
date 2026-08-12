CREATE TABLE IF NOT EXISTS curation_records
(
    record_id String,
    revision UInt32,
    target_type LowCardinality(String),
    target_id String,
    base_revision_id String,
    proposed_changes_json String,
    rationale String,
    citations Array(String),
    status LowCardinality(String),
    proposer_id String,
    reviewer_id String,
    review_note String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (record_id, revision);
