CREATE TABLE IF NOT EXISTS research_stage_stats
(
    event_type LowCardinality(String),
    stage LowCardinality(String),
    hour DateTime('UTC'),
    event_count AggregateFunction(count),
    average_duration AggregateFunction(avg, UInt32),
    duration_quantiles AggregateFunction(quantiles(0.5, 0.95), UInt32)
)
ENGINE = AggregatingMergeTree
ORDER BY (event_type, stage, hour);
