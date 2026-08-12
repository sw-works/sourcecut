CREATE TABLE IF NOT EXISTS formula_occurrences
(
    occurrence_id String,
    formula_id String,
    version_id LowCardinality(String),
    book UInt16,
    line_start UInt32,
    line_end UInt32,
    ngram_size UInt8,
    normalized_formula String,
    display_formula String,
    token_ids Array(String),
    occurrence_sha256 FixedString(64),
    derived_method LowCardinality(String),
    review_status LowCardinality(String),
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (version_id, ngram_size, normalized_formula, book, line_start, occurrence_id);
