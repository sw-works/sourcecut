CREATE TABLE IF NOT EXISTS curation_import_runs
(
    import_run_id String,
    idempotency_key FixedString(64),
    import_kind LowCardinality(String),
    upstream_revision String,
    manifest_sha256 FixedString(64),
    status LowCardinality(String),
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY idempotency_key;
