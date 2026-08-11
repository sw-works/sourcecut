CREATE OR REPLACE VIEW passage_lookup AS
SELECT
    passage_id,
    entry_id,
    source_id,
    author_id,
    author_display_name,
    entry_date,
    passage_index,
    char_start,
    char_end,
    passage_text,
    passage_sha256
FROM passages FINAL
WHERE passage_id = {pid:String}
LIMIT 2;
