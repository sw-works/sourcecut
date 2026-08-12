CREATE TABLE IF NOT EXISTS odyssey_claim_evidence
(
    claim_evidence_id String,
    claim_id String,
    support_role LowCardinality(String),
    source_kind LowCardinality(String),
    source_record_id String,
    version_id Nullable(String),
    source_quote String,
    source_start Nullable(UInt32),
    source_end Nullable(UInt32),
    citation String,
    validation_status LowCardinality(String),
    validation_errors Array(String),
    trusted Bool,
    validator_version LowCardinality(String),
    validated_at DateTime64(3, 'UTC'),
    source_version_hash Nullable(FixedString(64)),
    source_unit_hash Nullable(FixedString(64)),
    source_document_id String,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (claim_id, support_role, claim_evidence_id);
