CREATE TABLE IF NOT EXISTS research_sessions
(
    session_id String,
    status LowCardinality(String),
    prompt String,
    board_json String DEFAULT '',
    error String DEFAULT '',
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY session_id;
