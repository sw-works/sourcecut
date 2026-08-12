CREATE TABLE IF NOT EXISTS release_promotions
(
    promotion_id UUID,
    release_id String,
    action LowCardinality(String),
    actor_id String,
    reason String,
    occurred_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (occurred_at, promotion_id);
