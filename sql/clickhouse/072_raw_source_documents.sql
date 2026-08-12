CREATE TABLE IF NOT EXISTS raw_source_documents
(
    document_id String,
    version_id LowCardinality(String),
    media_type LowCardinality(String),
    raw_content String CODEC(ZSTD(3)),
    raw_sha256 FixedString(64),
    upstream_path String,
    upstream_revision LowCardinality(String),
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (version_id, document_id);
