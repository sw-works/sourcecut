CREATE TABLE IF NOT EXISTS scholarly_sources
(
    scholarly_source_id String,
    source_type LowCardinality(String),
    title String,
    creator_names Array(String),
    publication_year Nullable(UInt16),
    publisher String,
    doi Nullable(String),
    url String,
    license_id String,
    citation_text String,
    metadata JSON,
    review_status LowCardinality(String),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (review_status, scholarly_source_id);
