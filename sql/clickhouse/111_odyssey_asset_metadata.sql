CREATE TABLE IF NOT EXISTS odyssey_asset_metadata
(
    asset_id String, institution String, object_id String, culture String, period String,
    object_date String, object_begin_date Int32, object_end_date Int32, medium String,
    image_rights_status LowCardinality(String), image_attribution String, cached_image_path String,
    public_display Bool, release_id String, record_sha256 FixedString(64),
    updated_at DateTime64(3, 'UTC')
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY asset_id;
