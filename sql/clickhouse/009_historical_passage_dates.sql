CREATE OR REPLACE TABLE passages
(
    passage_id String,
    entry_id String,
    source_id String,
    author_id LowCardinality(String),
    author_display_name String,
    entry_date Int32,
    passage_index UInt16,
    char_start UInt32,
    char_end UInt32,
    passage_text String,
    passage_sha256 FixedString(64),
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (entry_date, author_id, entry_id, passage_index, passage_id);
