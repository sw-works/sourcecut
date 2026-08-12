from __future__ import annotations

import hashlib
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sourcecut_api.models.claim import (
    ClaimCreate,
    ClaimEvidence,
    ClaimMatrixRow,
    ClaimRecord,
    ClaimReviewStatus,
    ClaimSourceKind,
    ClaimTrace,
    EvidenceClass,
    EvidenceInput,
    PublicationDecision,
    SupportRole,
)

VALIDATOR_VERSION = "odyssey-claim-validator-v1"


class ClaimNotFoundError(KeyError):
    pass


class ClaimValidationService:
    def __init__(self, mcp_client_factory: Any) -> None:
        self._mcp_client_factory = mcp_client_factory
        self._claims: dict[str, ClaimRecord] = {}

    async def create(self, candidate: ClaimCreate) -> ClaimRecord:
        claim_id = f"odyssey-claim:{uuid4()}"
        now = datetime.now(UTC).isoformat()
        evidence = tuple(
            [
                await self._validate_evidence(claim_id, item)
                for item in candidate.evidence
            ]
        )
        translation_versions = tuple(
            sorted(
                {
                    item.version_id
                    for item in evidence
                    if item.version_id and not item.version_id.endswith("grc2")
                }
            )
        )
        translation_dependent = (
            candidate.evidence_class == EvidenceClass.TRANSLATION_WORDING
            or bool(translation_versions)
        )
        review_status = (
            ClaimReviewStatus.MACHINE_DERIVED
            if candidate.created_by_type == "model"
            else ClaimReviewStatus.DRAFT
        )
        record = ClaimRecord(
            claim_id=claim_id,
            claim_text=candidate.claim_text,
            claim_category=candidate.claim_category,
            evidence_class=candidate.evidence_class,
            confidence=candidate.confidence,
            review_status=review_status,
            translation_dependent=translation_dependent,
            translation_version_ids=translation_versions,
            created_by_type=candidate.created_by_type,
            created_by_id=candidate.created_by_id,
            model_id=candidate.model_id,
            prompt_hash=candidate.prompt_hash,
            schema_version=candidate.schema_version,
            validator_version=VALIDATOR_VERSION,
            unsupported_question=candidate.unsupported_question,
            evidence=evidence,
            created_at=now,
            updated_at=now,
        )
        self._claims[claim_id] = record
        return record

    def list(self) -> tuple[ClaimRecord, ...]:
        return tuple(sorted(self._claims.values(), key=lambda item: item.created_at))

    def get(self, claim_id: str) -> ClaimRecord:
        try:
            return self._claims[claim_id]
        except KeyError as error:
            raise ClaimNotFoundError(claim_id) from error

    def review(
        self,
        claim_id: str,
        *,
        status: ClaimReviewStatus,
        reviewer_id: str,
        note: str,
    ) -> ClaimRecord:
        record = self.get(claim_id)
        trusted_evidence = tuple(
            item.model_copy(
                update={
                    "trusted": status == ClaimReviewStatus.TRUSTED
                    and item.validation_status == "valid"
                }
            )
            for item in record.evidence
        )
        updated = record.model_copy(
            update={
                "review_status": status,
                "reviewer_id": reviewer_id,
                "review_note": note,
                "evidence": trusted_evidence,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        self._claims[claim_id] = updated
        return updated

    def publication_decision(self, claim_id: str) -> PublicationDecision:
        claim = self.get(claim_id)
        reasons = []
        if claim.evidence_class == EvidenceClass.UNSUPPORTED:
            reasons.append(
                "Unsupported questions are displayed as absences, not published as claims."
            )
        if claim.review_status != ClaimReviewStatus.TRUSTED:
            reasons.append("Claim review status is not trusted.")
        valid_exact = [
            item
            for item in claim.evidence
            if item.trusted
            and item.validation_status == "valid"
            and item.source_kind in {ClaimSourceKind.TEXT_SPAN, ClaimSourceKind.TOKEN_SPAN}
            and item.support_role == SupportRole.SUPPORTS
        ]
        if not valid_exact:
            reasons.append("No trusted, valid, exact supporting text span is attached.")
        if claim.evidence_class == EvidenceClass.PRIMARY_GREEK_EXPLICIT and not any(
            item.version_id and item.version_id.endswith("grc2") for item in valid_exact
        ):
            reasons.append("A Greek-wording claim requires a trusted Greek span.")
        if claim.evidence_class == EvidenceClass.TRANSLATION_WORDING and not (
            claim.translation_dependent and claim.translation_version_ids
        ):
            reasons.append("A translation-wording claim must identify its translation version.")
        return PublicationDecision(
            claim_id=claim_id,
            allowed=not reasons,
            reasons=tuple(reasons),
            checked_at=datetime.now(UTC).isoformat(),
        )

    def matrix(self) -> tuple[ClaimMatrixRow, ...]:
        rows = []
        for claim in self.list():
            grouped: dict[SupportRole, list[ClaimEvidence]] = defaultdict(list)
            for evidence in claim.evidence:
                grouped[evidence.support_role].append(evidence)
            limitations = []
            if claim.translation_dependent:
                limitations.append(
                    "Depends on wording in " + ", ".join(claim.translation_version_ids)
                )
            invalid = sum(item.validation_status != "valid" for item in claim.evidence)
            if invalid:
                limitations.append(f"{invalid} evidence link(s) failed exact validation")
            decision = self.publication_decision(claim.claim_id)
            rows.append(
                ClaimMatrixRow(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    evidence_class=claim.evidence_class,
                    confidence=claim.confidence,
                    review_status=claim.review_status,
                    translation_dependent=claim.translation_dependent,
                    supports=tuple(grouped[SupportRole.SUPPORTS]),
                    qualifies=tuple(grouped[SupportRole.QUALIFIES]),
                    conflicts=tuple(grouped[SupportRole.CONFLICTS]),
                    context=tuple(grouped[SupportRole.CONTEXT]),
                    limitations=tuple(limitations),
                    publication_ready=decision.allowed,
                )
            )
        return tuple(rows)

    async def trace(self, claim_id: str) -> ClaimTrace:
        claim = self.get(claim_id)
        chain = []
        for evidence in claim.evidence:
            source: dict[str, object] | None = None
            client = self._mcp_client_factory()
            if evidence.source_kind in {ClaimSourceKind.TEXT_SPAN, ClaimSourceKind.TOKEN_SPAN}:
                source_id = evidence.source_record_id
                token = None
                if evidence.source_kind == ClaimSourceKind.TOKEN_SPAN:
                    token_rows = (await client.get_odyssey_token(source_id))["rows"]
                    token = token_rows[0] if len(token_rows) == 1 else None
                    source_id = str(token["text_unit_id"]) if token else source_id
                rows = (await client.get_odyssey_claim_source(source_id))["rows"]
                source = rows[0] if len(rows) == 1 else None
                if token is not None and source is not None:
                    source = {**source, "token": token}
            elif evidence.source_kind == ClaimSourceKind.SCHOLARSHIP:
                rows = (
                    await client.get_odyssey_scholarly_source(evidence.source_record_id)
                )["rows"]
                source = rows[0] if len(rows) == 1 else None
            chain.append(
                {
                    "claim_id": claim_id,
                    "claim_evidence_id": evidence.claim_evidence_id,
                    "evidence": evidence.model_dump(mode="json"),
                    "source": source,
                }
            )
        return ClaimTrace(claim=claim, evidence_chain=tuple(chain))

    async def _validate_evidence(
        self, claim_id: str, evidence: EvidenceInput
    ) -> ClaimEvidence:
        errors = []
        source_version_hash = None
        source_unit_hash = None
        source_document_id = ""
        citation = evidence.citation
        if evidence.source_kind in {ClaimSourceKind.TEXT_SPAN, ClaimSourceKind.TOKEN_SPAN}:
            try:
                client = self._mcp_client_factory()
                token_row = None
                text_source_id = evidence.source_record_id
                if evidence.source_kind == ClaimSourceKind.TOKEN_SPAN:
                    token_rows = (await client.get_odyssey_token(evidence.source_record_id))["rows"]
                    if len(token_rows) != 1:
                        errors.append("Token source did not resolve uniquely")
                    else:
                        token_row = token_rows[0]
                        text_source_id = str(token_row["text_unit_id"])
                rows = (await client.get_odyssey_claim_source(text_source_id))["rows"]
            except ValueError as error:
                rows = []
                token_row = None
                errors.append(str(error))
            if len(rows) != 1:
                errors.append("Text source did not resolve uniquely")
            else:
                row = rows[0]
                normalized = str(row["normalized_text"])
                start = evidence.source_start or 0
                end = evidence.source_end or 0
                normalized_quote = unicodedata.normalize("NFC", evidence.source_quote)
                if end > len(normalized):
                    errors.append("Evidence offsets exceed the immutable text unit")
                elif normalized[start:end] != normalized_quote:
                    errors.append("Source quote does not match the exact normalized text span")
                if str(row["version_id"]) != evidence.version_id:
                    errors.append("Evidence version does not match the immutable text unit")
                if token_row is not None and (
                    int(token_row["char_start"]) != start
                    or int(token_row["char_end"]) != end
                    or unicodedata.normalize("NFC", str(token_row["surface"]))
                    != normalized_quote
                ):
                    errors.append("Token evidence does not match its aligned exact token span")
                citation = citation or str(row["citation"])
                source_version_hash = _optional_hash(row.get("source_version_hash"))
                source_unit_hash = _optional_hash(row.get("text_sha256"))
                source_document_id = str(row.get("source_document_id", ""))
        elif evidence.source_kind == ClaimSourceKind.SCHOLARSHIP:
            rows = (
                await self._mcp_client_factory().get_odyssey_scholarly_source(
                    evidence.source_record_id
                )
            )["rows"]
            if len(rows) != 1:
                errors.append("Scholarly source is absent or has not passed curation review")
            elif not citation:
                citation = str(rows[0]["citation_text"])
        else:
            errors.append(f"{evidence.source_kind} validation is owned by a later source adapter")

        now = datetime.now(UTC).isoformat()
        evidence_hash = hashlib.sha256(
            f"{claim_id}:{evidence.source_record_id}:{evidence.support_role}:{uuid4()}".encode()
        ).hexdigest()
        return ClaimEvidence(
            claim_evidence_id=f"claim-evidence:{evidence_hash[:28]}",
            claim_id=claim_id,
            support_role=evidence.support_role,
            source_kind=evidence.source_kind,
            source_record_id=evidence.source_record_id,
            version_id=evidence.version_id,
            source_quote=evidence.source_quote,
            source_start=evidence.source_start,
            source_end=evidence.source_end,
            citation=citation,
            validation_status="invalid" if errors else "valid",
            validation_errors=tuple(errors),
            validated_at=now,
            source_version_hash=source_version_hash,
            source_unit_hash=source_unit_hash,
            source_document_id=source_document_id,
        )


def _optional_hash(value: object) -> str | None:
    if value is None:
        return None
    text = value.decode("ascii") if isinstance(value, bytes) else str(value)
    return text if len(text) == 64 else None
