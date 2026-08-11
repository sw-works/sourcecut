CREATE OR REPLACE TABLE journal_entries
(
    entry_id String,
    source_id String,
    author_id LowCardinality(String),
    author_display_name String,
    entry_date Int32 CODEC(Delta, ZSTD),
    ordinal_for_day UInt16,
    heading String,
    raw_text String CODEC(ZSTD(3)),
    source_url String,
    source_locator String,
    raw_text_sha256 FixedString(64),
    parser_version LowCardinality(String),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY intDiv(entry_date, 10000)
ORDER BY (entry_date, author_id, ordinal_for_day, entry_id);
