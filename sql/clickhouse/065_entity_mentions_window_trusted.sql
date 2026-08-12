CREATE OR REPLACE VIEW entity_mentions_window AS
SELECT
    m.mention_id AS mention_id,
    m.entity_id AS entity_id,
    m.passage_id AS passage_id,
    m.entry_date AS entry_date,
    m.author_id AS author_id,
    p.author_display_name AS author_display_name,
    m.source_quote AS source_quote,
    m.source_start AS source_start,
    m.source_end AS source_end,
    m.extractor AS extractor,
    p.passage_text AS passage_text
FROM
(
    SELECT * FROM entity_mentions FINAL
    WHERE trusted = true AND validation_status = 'valid'
) AS m
INNER JOIN
(
    SELECT passage_id, author_display_name, passage_text FROM passages FINAL
) AS p ON p.passage_id = m.passage_id
WHERE m.entity_id = {entity:String}
  AND m.entry_date BETWEEN {start:Int32} AND {end:Int32}
ORDER BY m.entry_date, m.author_id, m.passage_id, m.mention_id
LIMIT 500;
