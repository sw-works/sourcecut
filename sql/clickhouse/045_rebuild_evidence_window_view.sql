CREATE OR REPLACE VIEW evidence_window AS
SELECT
    o.observation_id,
    o.passage_id AS passage_id,
    p.author_display_name,
    p.entry_date,
    o.category,
    o.canonical_term,
    o.source_quote,
    o.confidence
FROM
(
    SELECT passage_id, author_display_name, entry_date
    FROM passages FINAL
    WHERE entry_date BETWEEN {start:Int32} AND {end:Int32}
) AS p
INNER JOIN
(
    SELECT observation_id, passage_id, category, canonical_term, source_quote, confidence
    FROM observations FINAL
) AS o ON o.passage_id = p.passage_id
ORDER BY o.category, o.canonical_term, p.author_display_name, o.observation_id
LIMIT {limit:UInt16};
