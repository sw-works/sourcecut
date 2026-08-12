CREATE VIEW IF NOT EXISTS odyssey_lemma_occurrences_v AS
SELECT
    t.token_id,
    t.text_unit_id,
    t.version_id,
    t.book,
    t.line,
    t.token_index,
    t.surface,
    t.normalized_surface,
    t.accentless_surface,
    t.lemma,
    t.lemma_search,
    t.part_of_speech,
    t.morphology,
    t.char_start,
    t.char_end,
    t.annotation_source,
    t.annotation_confidence,
    t.review_status,
    t.annotation_version,
    u.citation,
    u.cts_urn,
    u.original_text
FROM text_tokens AS t FINAL
INNER JOIN text_units AS u FINAL ON u.text_unit_id = t.text_unit_id
WHERE t.version_id = 'odyssey-perseus-grc2';
