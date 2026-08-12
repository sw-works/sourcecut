CREATE TABLE IF NOT EXISTS corpus_releases
(
    release_id String,
    release_json String,
    status LowCardinality(String),
    upstream_revision String,
    created_at DateTime64(3, 'UTC'),
    promoted_at Nullable(DateTime64(3, 'UTC')),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY release_id;
