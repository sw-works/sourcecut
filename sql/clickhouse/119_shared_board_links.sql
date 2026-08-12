CREATE TABLE IF NOT EXISTS shared_board_links
(
    share_id String,
    board_id String,
    revision_id String,
    snapshot_json String,
    manifest_sha256 FixedString(64),
    omitted_item_count UInt16,
    expires_at DateTime64(3, 'UTC'),
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY (board_id, created_at, share_id);
