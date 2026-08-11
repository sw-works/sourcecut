CREATE TABLE IF NOT EXISTS term_expansions
(
    category LowCardinality(String),
    term String,
    expansions Array(String),
    notes String DEFAULT '',
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (category, term);
