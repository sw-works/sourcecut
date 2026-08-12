CREATE OR REPLACE VIEW odyssey_entity_occurrences_v AS
SELECT e.entity_id AS entity_id, e.entity_type AS entity_type,
       e.canonical_name AS canonical_name, e.greek_name AS greek_name,
       e.aliases AS aliases, e.description AS description,
       e.authority_uris AS authority_uris, e.curation_citations AS curation_citations,
       m.mention_id AS mention_id, m.text_unit_id AS text_unit_id,
       m.version_id AS version_id, m.book AS book, m.line_start AS line_start,
       m.line_end AS line_end, m.surface AS surface, m.char_start AS char_start,
       m.char_end AS char_end, m.mention_role AS mention_role, m.confidence AS confidence,
       u.citation AS citation, u.cts_urn AS cts_urn, u.original_text AS original_text
FROM classical_entities AS e FINAL
LEFT JOIN classical_entity_mentions AS m FINAL ON m.entity_id = e.entity_id
LEFT JOIN text_units AS u FINAL ON u.text_unit_id = m.text_unit_id
WHERE e.status = 'trusted' AND (m.review_status = 'deterministic_alias_match' OR m.mention_id IS NULL);
