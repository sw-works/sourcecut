CREATE TABLE IF NOT EXISTS linguistic_annotation_releases
(
    annotation_release_id String,
    work_id LowCardinality(String),
    source_version_id LowCardinality(String),
    annotation_source LowCardinality(String),
    annotation_version LowCardinality(String),
    source_document_urn String,
    repository_url String,
    upstream_path String,
    upstream_revision FixedString(40),
    source_sha256 FixedString(64),
    license_id LowCardinality(String),
    raw_content String CODEC(ZSTD(3)),
    review_status LowCardinality(String),
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (work_id, annotation_release_id);
