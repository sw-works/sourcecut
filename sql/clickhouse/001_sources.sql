CREATE TABLE IF NOT EXISTS sources
(
    source_id String,
    provider LowCardinality(String),
    title String,
    source_url String,
    edition_notes String DEFAULT '',
    rights_status LowCardinality(String),
    raw_metadata String DEFAULT '{}',
    content_sha256 FixedString(64),
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY source_id;
