CREATE TABLE IF NOT EXISTS themes
(
    theme_id String, title String, description String, aliases Array(String),
    bibliography Array(String), curator String, status LowCardinality(String), version String,
    release_id String, record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY theme_id;
