CREATE TABLE IF NOT EXISTS event_passages
(
    event_passage_id String,
    event_id String,
    version_id LowCardinality(String),
    book UInt16,
    line_start UInt32,
    line_end UInt32,
    relationship LowCardinality(String),
    evidence_class LowCardinality(String),
    review_status LowCardinality(String),
    release_id String,
    record_sha256 FixedString(64),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (version_id, book, line_start, event_id, event_passage_id);
