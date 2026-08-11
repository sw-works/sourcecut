CREATE TABLE IF NOT EXISTS entities
(
    entity_id String,
    entity_type LowCardinality(String),
    canonical_name String,
    alt_names Array(String),
    notes String DEFAULT '',
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY entity_id;
