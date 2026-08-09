CREATE TABLE IF NOT EXISTS passages
(
    passage_id String,
    entry_id String,
    source_id String,
    author_id LowCardinality(String),
    author_display_name String,
    entry_date Date,
    passage_index UInt16,
    char_start UInt32,
    char_end UInt32,
    passage_text String,
    passage_sha256 FixedString(64),
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYear(entry_date)
ORDER BY (entry_date, author_id, entry_id, passage_index, passage_id);
