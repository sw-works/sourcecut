CREATE TABLE IF NOT EXISTS text_units
(
    text_unit_id String,
    work_id LowCardinality(String),
    version_id LowCardinality(String),
    book UInt16,
    line_start UInt32,
    line_end UInt32,
    source_line_start UInt32,
    source_line_end UInt32,
    citation_correction String DEFAULT '',
    citation String,
    cts_urn String,
    unit_index UInt32,
    original_text String CODEC(ZSTD(3)),
    normalized_text String CODEC(ZSTD(3)),
    source_document_id String,
    source_char_start UInt64 DEFAULT 0,
    source_char_end UInt64 DEFAULT 0,
    text_sha256 FixedString(64),
    parser_version LowCardinality(String),
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (version_id, book, line_start, text_unit_id);
