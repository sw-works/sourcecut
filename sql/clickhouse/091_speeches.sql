CREATE TABLE IF NOT EXISTS speeches
(
    speech_id String,
    work_id LowCardinality(String),
    speaker_entity_id String,
    addressee_entity_ids Array(String),
    audience_entity_ids Array(String),
    narrator_entity_id String,
    narrative_level LowCardinality(String),
    book UInt16,
    line_start UInt32,
    line_end UInt32,
    speech_type LowCardinality(String),
    evidence_status LowCardinality(String),
    review_status LowCardinality(String),
    release_id String,
    record_sha256 FixedString(64),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (work_id, book, line_start, speech_id);
