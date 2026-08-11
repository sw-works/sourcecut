CREATE OR REPLACE TABLE passages
(
    passage_id String,
    entry_id String,
    source_id String,
    author_id LowCardinality(String),
    author_display_name String,
    entry_date Int32 CODEC(Delta, ZSTD),
    passage_index UInt16,
    char_start UInt32,
    char_end UInt32,
    passage_text String CODEC(ZSTD(3)),
    passage_sha256 FixedString(64),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD),
    INDEX idx_passage_text_lower_tokens lower(passage_text)
        TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 4,
    PROJECTION by_passage_id (SELECT * ORDER BY passage_id)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY intDiv(entry_date, 10000)
ORDER BY (entry_date, author_id, entry_id, passage_index, passage_id)
SETTINGS deduplicate_merge_projection_mode = 'rebuild';
