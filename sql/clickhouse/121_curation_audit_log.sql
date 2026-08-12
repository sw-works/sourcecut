CREATE TABLE IF NOT EXISTS curation_audit_log
(
    audit_id UUID,
    action LowCardinality(String),
    actor_id String,
    target_type LowCardinality(String),
    target_id String,
    before_revision String,
    after_revision String,
    detail_json String,
    occurred_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (occurred_at, audit_id);
