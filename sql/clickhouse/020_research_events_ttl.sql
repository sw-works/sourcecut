ALTER TABLE research_events MODIFY TTL occurred_at + INTERVAL 90 DAY DELETE;
