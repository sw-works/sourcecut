CREATE OR REPLACE VIEW author_date_matrix AS
SELECT
    e.author_id AS author_id,
    e.author_display_name AS author_display_name,
    e.entry_date AS entry_date,
    countIf(arrayExists(t -> hasToken(lower(p.passage_text), t), {terms:Array(String)})) AS mention_count,
    countIf(o.observation_id != '') AS observation_count,
    groupUniqArrayIf(p.passage_id, arrayExists(t -> hasToken(lower(p.passage_text), t), {terms:Array(String)})) AS passage_ids
FROM
(
    SELECT author_id, author_display_name, entry_date
    FROM journal_entries FINAL
    WHERE entry_date BETWEEN {start:Int32} AND {end:Int32}
    GROUP BY author_id, author_display_name, entry_date
) AS e
LEFT JOIN
(
    SELECT passage_id, author_id, entry_date, passage_text
    FROM passages FINAL
    WHERE entry_date BETWEEN {start:Int32} AND {end:Int32}
) AS p ON p.author_id = e.author_id AND p.entry_date = e.entry_date
LEFT JOIN
(
    SELECT observation_id, passage_id
    FROM observations FINAL
    WHERE trusted = true AND validation_status = 'valid'
      AND lower(canonical_term) IN {terms:Array(String)}
) AS o ON o.passage_id = p.passage_id
GROUP BY e.author_id, e.author_display_name, e.entry_date
ORDER BY e.author_display_name, e.entry_date
LIMIT 500;
