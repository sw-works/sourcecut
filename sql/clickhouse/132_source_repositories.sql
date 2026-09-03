CREATE TABLE IF NOT EXISTS source_repositories
(
    repository_id LowCardinality(String),
    display_name String,
    base_url String,
    adapter LowCardinality(String),
    rights_field String,
    eligible_values Array(String),
    default_license_id LowCardinality(String),
    rate_limit_per_minute UInt16 DEFAULT 30,
    terms_note String DEFAULT '',
    notes String DEFAULT '',
    reviewed_by String,
    reviewed_at DateTime64(3, 'UTC'),
    probed_at Nullable(DateTime64(3, 'UTC')),
    probe_sample_size UInt16 DEFAULT 0,
    probe_match_rate Float32 DEFAULT 0,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY repository_id;
