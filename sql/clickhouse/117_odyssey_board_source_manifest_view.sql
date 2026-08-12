CREATE VIEW IF NOT EXISTS odyssey_board_source_manifest_v AS
SELECT
    board_id,
    revision_id,
    release_manifest_id,
    source_session_id,
    created_at
FROM board_revisions
WHERE JSONExtractString(document_json, 'corpus_id') = 'odyssey';
