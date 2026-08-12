CREATE TABLE IF NOT EXISTS classical_passages
(
    passage_id String,
    version_id LowCardinality(String),
    book UInt16,
    line_start UInt32,
    line_end UInt32,
    unit_ids Array(String),
    passage_text String CODEC(ZSTD(3)),
    passage_sha256 FixedString(64),
    segmentation_version LowCardinality(String),
    embedding Array(Float32) DEFAULT [],
    embedding_model LowCardinality(String) DEFAULT '',
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (version_id, book, line_start, passage_id);
