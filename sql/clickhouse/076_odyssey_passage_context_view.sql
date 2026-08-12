CREATE VIEW IF NOT EXISTS odyssey_passage_context_v AS
SELECT
    passage_id,
    version_id,
    book,
    line_start,
    line_end,
    unit_ids,
    passage_text,
    passage_sha256,
    segmentation_version
FROM classical_passages FINAL;
