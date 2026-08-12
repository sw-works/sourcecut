CREATE TABLE IF NOT EXISTS works
(
    work_id String,
    corpus_id LowCardinality(String),
    cts_work_urn String,
    author_display_name LowCardinality(String),
    title String,
    original_language LowCardinality(String),
    book_count UInt16,
    metadata JSON,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (corpus_id, original_language, work_id);
