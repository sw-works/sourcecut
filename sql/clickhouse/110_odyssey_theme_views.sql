CREATE VIEW IF NOT EXISTS odyssey_theme_passages_v AS
SELECT t.theme_id, t.title, t.description, t.aliases, t.bibliography, t.curator,
       p.theme_passage_id, p.rationale, p.evidence_class, p.text_unit_id,
       u.version_id, u.book, u.line_start, u.line_end, u.citation, u.cts_urn, u.original_text
FROM themes AS t FINAL
LEFT JOIN theme_passages AS p FINAL ON p.theme_id = t.theme_id
LEFT JOIN text_units AS u FINAL ON u.text_unit_id = p.text_unit_id
WHERE t.status = 'trusted' AND (p.review_status = 'trusted' OR p.theme_passage_id IS NULL);
