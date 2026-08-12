CREATE TABLE IF NOT EXISTS narrative_events
(
    event_id String,
    work_id LowCardinality(String),
    title String,
    summary String,
    event_type LowCardinality(String),
    reading_order_start UInt32,
    reading_order_end UInt32,
    story_order_start Decimal64(6),
    story_order_end Decimal64(6),
    duration_value Nullable(Float64),
    duration_unit LowCardinality(String),
    duration_certainty LowCardinality(String),
    duration_source_note String,
    narrative_level LowCardinality(String),
    narrator_entity_id String,
    participant_entity_ids Array(String),
    place_ids Array(String),
    theme_ids Array(String),
    parent_event_id Nullable(String),
    review_status LowCardinality(String),
    release_id String,
    record_sha256 FixedString(64),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (work_id, reading_order_start, event_id);
