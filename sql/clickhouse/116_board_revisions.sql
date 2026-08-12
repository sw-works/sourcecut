CREATE TABLE IF NOT EXISTS board_revisions
(
    revision_id String,
    board_id String,
    parent_revision_id String,
    revision_kind LowCardinality(String),
    document_json String,
    release_manifest_id String,
    changed_fields Array(String),
    actor String,
    source_session_id String,
    trace_json String,
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (board_id, created_at, revision_id);
