CREATE TABLE IF NOT EXISTS route_nodes
(
    route_node_id String, hypothesis_id String, event_id String, poetic_place_id String,
    identification_id Nullable(String), sequence_index Decimal64(6), node_kind String,
    longitude Nullable(Float64), latitude Nullable(Float64), display_region String,
    citation_ids Array(String), review_status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (hypothesis_id, sequence_index, route_node_id);
