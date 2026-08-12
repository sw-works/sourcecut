CREATE TABLE IF NOT EXISTS source_versions
(
    version_id String,
    work_id LowCardinality(String),
    cts_version_urn String,
    version_type Enum8('edition' = 1, 'translation' = 2, 'commentary' = 3, 'witness' = 4),
    language LowCardinality(String),
    label String,
    editor_names Array(String),
    translator_names Array(String),
    bibliographic_description String,
    publication_year UInt16 DEFAULT 0,
    source_url String,
    upstream_revision LowCardinality(String),
    license_id LowCardinality(String),
    display_decision LowCardinality(String),
    source_sha256 Nullable(FixedString(64)),
    raw_manifest JSON,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (work_id, version_type, language, version_id);
