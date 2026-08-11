CREATE TABLE IF NOT EXISTS entity_mentions
(
    mention_id String,
    entity_id String,
    passage_id String,
    entry_date Int32,
    author_id LowCardinality(String),
    source_quote String,
    source_start UInt32,
    source_end UInt32,
    trusted Bool DEFAULT false,
    validation_status LowCardinality(String) DEFAULT 'invalid',
    extractor LowCardinality(String),
    model LowCardinality(String),
    schema_version LowCardinality(String),
    prompt_version LowCardinality(String),
    created_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (entity_id, entry_date, passage_id, mention_id);
