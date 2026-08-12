CREATE TABLE IF NOT EXISTS licenses
(
    license_id String,
    spdx_or_rights_code LowCardinality(String),
    display_name String,
    canonical_url String,
    attribution_template String,
    share_alike Bool,
    commercial_use_allowed Int8 DEFAULT -1,
    derivatives_allowed Int8 DEFAULT -1,
    bulk_export_allowed Int8 DEFAULT -1,
    notes String DEFAULT '',
    reviewed_by String DEFAULT '',
    reviewed_at DateTime64(3, 'UTC') DEFAULT toDateTime64(0, 3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (spdx_or_rights_code, license_id);
