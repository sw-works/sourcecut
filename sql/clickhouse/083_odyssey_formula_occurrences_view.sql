CREATE VIEW IF NOT EXISTS odyssey_formula_occurrences_v AS
SELECT
    formula_id,
    any(display_formula) AS display_formula,
    normalized_formula,
    ngram_size,
    count() AS occurrence_count,
    arraySlice(arraySort(groupArray((book, line_start, line_end, occurrence_id))), 1, 50) AS occurrences
FROM formula_occurrences FINAL
WHERE version_id = 'odyssey-perseus-grc2'
GROUP BY formula_id, normalized_formula, ngram_size;
