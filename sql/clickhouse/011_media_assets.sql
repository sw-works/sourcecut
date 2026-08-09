CREATE TABLE IF NOT EXISTS media_assets
(
    asset_id String,
    provider LowCardinality(String),
    provider_id String,
    title String,
    description String DEFAULT '',
    creators Array(String),
    asset_type LowCardinality(String),
    creation_date_text String DEFAULT '',
    creation_year UInt16 DEFAULT 0,
    subjects Array(String),
    places Array(String),
    source_url String,
    media_url String DEFAULT '',
    thumbnail_path String DEFAULT '',
    rights_status LowCardinality(String),
    rights_text String DEFAULT '',
    historical_relationship LowCardinality(String),
    raw_metadata String,
    metadata_sha256 FixedString(64),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (provider, rights_status, asset_type, creation_year, asset_id);
