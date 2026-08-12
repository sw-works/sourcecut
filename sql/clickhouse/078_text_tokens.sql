CREATE TABLE IF NOT EXISTS text_tokens
(
    token_id String,
    text_unit_id String,
    version_id LowCardinality(String),
    book UInt16,
    line UInt32,
    token_index UInt16,
    surface String,
    normalized_surface String,
    accentless_surface String,
    lemma String,
    lemma_search String,
    part_of_speech LowCardinality(String),
    morphology JSON,
    char_start UInt32,
    char_end UInt32,
    annotation_source LowCardinality(String),
    annotation_confidence Float32,
    review_status LowCardinality(String),
    annotation_version LowCardinality(String),
    annotation_release_id String,
    source_token_ref String,
    token_sha256 FixedString(64),
    updated_at DateTime64(3, 'UTC'),
    INDEX idx_token_surface accentless_surface TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 1,
    INDEX idx_token_lemma lemma_search TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 1
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (version_id, book, line, token_index, token_id);
