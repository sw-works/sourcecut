CREATE TABLE IF NOT EXISTS saved_searches
(
    saved_search_id String,
    owner_id String,
    corpus_id LowCardinality(String),
    name String,
    normalized_query String,
    request_json String CODEC(ZSTD(3)),
    result_reference_ids Array(String),
    board_id String DEFAULT '',
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (owner_id, corpus_id, saved_search_id);
