CREATE OR REPLACE VIEW author_term_presence AS
SELECT
    author_id,
    author_display_name,
    countIf(hasToken(lower(passage_text), lower({term:String}))) AS mention_count,
    groupArrayIf(passage_id, hasToken(lower(passage_text), lower({term:String}))) AS passage_ids
FROM passages FINAL
WHERE entry_date BETWEEN {start:Int32} AND {end:Int32}
GROUP BY author_id, author_display_name
ORDER BY author_display_name
LIMIT 200;
