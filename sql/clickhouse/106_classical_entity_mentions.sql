CREATE TABLE IF NOT EXISTS classical_entity_mentions
(
    mention_id String, entity_id String, text_unit_id String, version_id String,
    book UInt16, line_start UInt32, line_end UInt32, surface String,
    char_start UInt32, char_end UInt32, mention_role LowCardinality(String),
    confidence Float32, review_status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (entity_id, version_id, book, line_start, mention_id);
