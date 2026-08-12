CREATE VIEW IF NOT EXISTS odyssey_event_timeline_v AS
SELECT
    e.event_id,
    e.title,
    e.summary,
    e.event_type,
    e.reading_order_start,
    e.reading_order_end,
    e.story_order_start,
    e.story_order_end,
    e.duration_value,
    e.duration_unit,
    e.duration_certainty,
    e.duration_source_note,
    e.narrative_level,
    e.narrator_entity_id,
    e.participant_entity_ids,
    e.place_ids,
    e.theme_ids,
    e.parent_event_id,
    groupArray((p.version_id, p.book, p.line_start, p.line_end, p.relationship, p.evidence_class)) AS passages
FROM narrative_events FINAL AS e
INNER JOIN event_passages FINAL AS p ON p.event_id = e.event_id
WHERE e.work_id = 'odyssey'
  AND e.review_status = 'trusted'
  AND p.review_status = 'trusted'
GROUP BY
    e.event_id, e.title, e.summary, e.event_type, e.reading_order_start,
    e.reading_order_end, e.story_order_start, e.story_order_end, e.duration_value,
    e.duration_unit, e.duration_certainty, e.duration_source_note, e.narrative_level,
    e.narrator_entity_id, e.participant_entity_ids, e.place_ids, e.theme_ids,
    e.parent_event_id;
