CREATE TABLE IF NOT EXISTS research_boards
(
    board_id String,
    corpus_id LowCardinality(String),
    current_revision_id String,
    document_json String,
    release_manifest_id String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY board_id;
