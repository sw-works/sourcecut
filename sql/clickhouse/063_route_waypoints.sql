CREATE TABLE IF NOT EXISTS route_waypoints
(
    waypoint_id String,
    entry_date Int32,
    name String,
    lat Float64,
    lon Float64,
    citation_passage_ids Array(String),
    source_note String,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (entry_date, waypoint_id);
