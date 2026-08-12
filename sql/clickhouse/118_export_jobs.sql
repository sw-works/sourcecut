CREATE TABLE IF NOT EXISTS export_jobs
(
    job_id String,
    board_id String,
    revision_id String,
    format LowCardinality(String),
    display_policy LowCardinality(String),
    rights_decision String,
    status LowCardinality(String),
    artifact_reference String,
    artifact_sha256 FixedString(64),
    manifest_sha256 FixedString(64),
    expires_at DateTime64(3, 'UTC'),
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (board_id, created_at, job_id);
