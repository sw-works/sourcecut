CREATE TABLE IF NOT EXISTS odyssey_claims
(
    claim_id String,
    corpus_id LowCardinality(String),
    claim_text String,
    claim_category LowCardinality(String),
    evidence_class LowCardinality(String),
    confidence LowCardinality(String),
    review_status LowCardinality(String),
    translation_dependent Bool,
    translation_version_ids Array(String),
    created_by_type LowCardinality(String),
    created_by_id String,
    model_id LowCardinality(String),
    prompt_hash Nullable(FixedString(64)),
    schema_version LowCardinality(String),
    validator_version LowCardinality(String),
    reviewer_id String,
    review_note String,
    unsupported_question String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (corpus_id, review_status, claim_id);
