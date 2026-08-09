CREATE TABLE IF NOT EXISTS research_events
(
    event_id String,
    session_id String,
    event_type LowCardinality(String),
    stage LowCardinality(String),
    status LowCardinality(String),
    message String,
    payload_json String DEFAULT '{}',
    occurred_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (session_id, occurred_at, event_id);
