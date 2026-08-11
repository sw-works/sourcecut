CREATE MATERIALIZED VIEW IF NOT EXISTS research_stage_stats_mv
TO research_stage_stats AS
SELECT
    event_type,
    stage,
    toStartOfHour(occurred_at) AS hour,
    countState() AS event_count,
    avgState(duration_ms) AS average_duration,
    quantilesState(0.5, 0.95)(duration_ms) AS duration_quantiles
FROM research_events
GROUP BY event_type, stage, hour;
