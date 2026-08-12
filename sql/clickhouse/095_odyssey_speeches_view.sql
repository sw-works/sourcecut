CREATE VIEW IF NOT EXISTS odyssey_speeches_v AS
SELECT
    speech_id,
    speaker_entity_id,
    addressee_entity_ids,
    audience_entity_ids,
    narrator_entity_id,
    narrative_level,
    book,
    line_start,
    line_end,
    speech_type
FROM speeches FINAL
WHERE work_id = 'odyssey'
  AND review_status = 'trusted'
  AND evidence_status = 'exact_range';
