CREATE TABLE IF NOT EXISTS classical_entities
(
    entity_id String, entity_type LowCardinality(String), canonical_name String,
    greek_name String, aliases Array(String), description String, authority_uris Array(String),
    curation_citations Array(String), status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (entity_type, entity_id);
