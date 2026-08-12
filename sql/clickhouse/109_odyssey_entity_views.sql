CREATE VIEW IF NOT EXISTS odyssey_entity_occurrences_v AS
SELECT e.entity_id, e.entity_type, e.canonical_name, e.greek_name, e.aliases,
       e.description, e.authority_uris, e.curation_citations,
       m.mention_id, m.text_unit_id, m.version_id, m.book, m.line_start, m.line_end,
       m.surface, m.char_start, m.char_end, m.mention_role, m.confidence,
       u.citation, u.cts_urn, u.original_text
FROM classical_entities FINAL AS e
LEFT JOIN classical_entity_mentions FINAL AS m ON m.entity_id = e.entity_id
LEFT JOIN text_units FINAL AS u ON u.text_unit_id = m.text_unit_id
WHERE e.status = 'trusted' AND (m.review_status = 'deterministic_alias_match' OR m.mention_id IS NULL);
