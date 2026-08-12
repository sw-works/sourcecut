CREATE VIEW IF NOT EXISTS odyssey_trusted_claim_evidence_v AS
SELECT
    c.claim_id,
    c.claim_text,
    c.claim_category,
    c.evidence_class,
    c.confidence,
    c.translation_dependent,
    c.translation_version_ids,
    e.claim_evidence_id,
    e.support_role,
    e.source_kind,
    e.source_record_id,
    e.version_id,
    e.source_quote,
    e.source_start,
    e.source_end,
    e.citation,
    e.source_version_hash,
    e.source_unit_hash,
    e.source_document_id
FROM odyssey_claims FINAL AS c
INNER JOIN odyssey_claim_evidence FINAL AS e ON e.claim_id = c.claim_id
WHERE c.corpus_id = 'odyssey'
  AND c.review_status = 'trusted'
  AND e.trusted = true
  AND e.validation_status = 'valid';
