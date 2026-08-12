CREATE TABLE IF NOT EXISTS poetic_places
(
    poetic_place_id String, work_id LowCardinality(String) DEFAULT 'odyssey',
    canonical_name String, place_class LowCardinality(String), default_map_behavior String,
    description String, review_status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (work_id, poetic_place_id);
