CREATE TABLE IF NOT EXISTS route_edges
(
    route_edge_id String, hypothesis_id String, from_node_id String, to_node_id String,
    edge_kind LowCardinality(String), sequence_index Decimal64(6), certainty String,
    citation_ids Array(String), review_status LowCardinality(String), release_id String,
    record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (hypothesis_id, sequence_index, route_edge_id);
