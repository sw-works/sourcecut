CREATE TABLE IF NOT EXISTS ancient_places
(
    place_id String, canonical_name String, aliases Array(String), pleiades_uri String,
    representative_lon Float64, representative_lat Float64,
    coordinate_certainty LowCardinality(String), authority_source String,
    source_release String, license_id String, release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY place_id;
