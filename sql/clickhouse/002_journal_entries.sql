CREATE TABLE IF NOT EXISTS journal_entries
(
    entry_id String,
    source_id String,
    author_id LowCardinality(String),
    author_display_name String,
    entry_date Date,
    ordinal_for_day UInt16,
    heading String,
    raw_text String,
    source_url String,
    source_locator String,
    raw_text_sha256 FixedString(64),
    parser_version LowCardinality(String),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYear(entry_date)
ORDER BY (entry_date, author_id, ordinal_for_day, entry_id);
