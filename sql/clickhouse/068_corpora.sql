CREATE TABLE IF NOT EXISTS corpora
(
    corpus_id String,
    title String,
    description String,
    default_work_id String,
    adapter_version LowCardinality(String),
    display_policy LowCardinality(String),
    status LowCardinality(String),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (status, corpus_id);
