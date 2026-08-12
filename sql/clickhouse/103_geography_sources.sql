CREATE TABLE IF NOT EXISTS geography_sources
(
    source_id String, citation String, url String, release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY source_id;
