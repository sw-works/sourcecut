CREATE TABLE IF NOT EXISTS derived_rebuild_jobs
(
    rebuild_id UUID,
    layer LowCardinality(String),
    source_version_ids Array(String),
    source_mutations UInt8 DEFAULT 0,
    status LowCardinality(String),
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (created_at, rebuild_id);
