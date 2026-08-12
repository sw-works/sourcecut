CREATE VIEW IF NOT EXISTS odyssey_event_passages_v AS
SELECT
    p.event_passage_id,
    p.event_id,
    p.version_id,
    p.book,
    p.line_start,
    p.line_end,
    p.relationship,
    e.event_type,
    e.narrative_level,
    e.participant_entity_ids,
    e.place_ids,
    e.theme_ids
FROM event_passages AS p FINAL
INNER JOIN narrative_events AS e FINAL ON e.event_id = p.event_id
WHERE e.work_id = 'odyssey'
  AND e.review_status = 'trusted'
  AND p.review_status = 'trusted';
