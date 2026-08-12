CREATE TABLE IF NOT EXISTS asset_corpus_links
(
    asset_link_id String, asset_id String, corpus_id String, target_kind LowCardinality(String),
    target_id String, relationship_class LowCardinality(String), review_status LowCardinality(String),
    release_id String, record_sha256 FixedString(64), updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (corpus_id, target_kind, target_id, asset_id, asset_link_id);
