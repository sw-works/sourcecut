from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sourcecut_api.models.corpus import Sha256


class EvidenceClass(StrEnum):
    PRIMARY_GREEK_EXPLICIT = "PRIMARY_GREEK_EXPLICIT"
    TRANSLATION_WORDING = "TRANSLATION_WORDING"
    TEXTUAL_INFERENCE = "TEXTUAL_INFERENCE"
    VARIANT_READING = "VARIANT_READING"
    SCHOLIA_OR_ANCIENT_COMMENTARY = "SCHOLIA_OR_ANCIENT_COMMENTARY"
    MODERN_SCHOLARLY_INTERPRETATION = "MODERN_SCHOLARLY_INTERPRETATION"
    TRADITIONAL_IDENTIFICATION = "TRADITIONAL_IDENTIFICATION"
    SCHOLARLY_GEOGRAPHIC_HYPOTHESIS = "SCHOLARLY_GEOGRAPHIC_HYPOTHESIS"
    MATERIAL_OBJECT_RECORD = "MATERIAL_OBJECT_RECORD"
    LATER_RECEPTION = "LATER_RECEPTION"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    UNSUPPORTED = "UNSUPPORTED"


class ClaimConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class ClaimReviewStatus(StrEnum):
    DRAFT = "draft"
    MACHINE_DERIVED = "machine_derived"
    REVIEWED = "reviewed"
    TRUSTED = "trusted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class SupportRole(StrEnum):
    SUPPORTS = "supports"
    QUALIFIES = "qualifies"
    CONFLICTS = "conflicts"
    CONTEXT = "context"


class ClaimSourceKind(StrEnum):
    TEXT_SPAN = "text_span"
    TOKEN_SPAN = "token_span"
    SCHOLARSHIP = "scholarship"
    OBJECT = "object"
    IDENTIFICATION = "identification"


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support_role: SupportRole
    source_kind: ClaimSourceKind
    source_record_id: Annotated[str, Field(min_length=1, max_length=300)]
    version_id: str | None = None
    source_quote: Annotated[str, Field(max_length=5_000)] = ""
    source_start: Annotated[int | None, Field(ge=0)] = None
    source_end: Annotated[int | None, Field(ge=0)] = None
    citation: Annotated[str, Field(max_length=500)] = ""

    @model_validator(mode="after")
    def validate_span_contract(self) -> EvidenceInput:
        if self.source_kind in {ClaimSourceKind.TEXT_SPAN, ClaimSourceKind.TOKEN_SPAN}:
            if not self.version_id or not self.source_quote:
                raise ValueError("Text evidence requires version_id and source_quote")
            if self.source_start is None or self.source_end is None:
                raise ValueError("Text evidence requires exact source offsets")
            if self.source_end <= self.source_start:
                raise ValueError("Text evidence source range is empty or reversed")
        return self


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_text: Annotated[str, Field(min_length=5, max_length=2_000)]
    claim_category: Annotated[str, Field(min_length=1, max_length=100)]
    evidence_class: EvidenceClass
    confidence: ClaimConfidence
    evidence: tuple[EvidenceInput, ...] = ()
    created_by_type: str = "human"
    created_by_id: str = "local-preview"
    model_id: str = ""
    prompt_hash: Sha256 | None = None
    schema_version: str = "odyssey-claim-v1"
    unsupported_question: str = ""

    @model_validator(mode="after")
    def validate_supported_state(self) -> ClaimCreate:
        if self.evidence_class == EvidenceClass.UNSUPPORTED:
            if self.evidence:
                raise ValueError("Unsupported claims cannot attach support evidence")
            if not self.unsupported_question:
                raise ValueError("Unsupported claims must preserve the unanswered question")
            if self.confidence != ClaimConfidence.UNKNOWN:
                raise ValueError("Unsupported claims must use UNKNOWN confidence")
        elif not self.evidence:
            raise ValueError("Supported claims require at least one evidence link")
        return self


class ClaimEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_evidence_id: str
    claim_id: str
    support_role: SupportRole
    source_kind: ClaimSourceKind
    source_record_id: str
    version_id: str | None
    source_quote: str
    source_start: int | None
    source_end: int | None
    citation: str
    validation_status: str
    validation_errors: tuple[str, ...] = ()
    trusted: bool = False
    validator_version: str = "odyssey-claim-validator-v1"
    validated_at: str
    source_version_hash: Sha256 | None = None
    source_unit_hash: Sha256 | None = None
    source_document_id: str = ""


class ClaimRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    corpus_id: str = "odyssey"
    claim_text: str
    claim_category: str
    evidence_class: EvidenceClass
    confidence: ClaimConfidence
    review_status: ClaimReviewStatus
    translation_dependent: bool
    translation_version_ids: tuple[str, ...]
    created_by_type: str
    created_by_id: str
    model_id: str
    prompt_hash: Sha256 | None
    schema_version: str
    validator_version: str
    reviewer_id: str = ""
    review_note: str = ""
    unsupported_question: str = ""
    evidence: tuple[ClaimEvidence, ...]
    created_at: str
    updated_at: str


class ClaimMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    claim_text: str
    evidence_class: EvidenceClass
    confidence: ClaimConfidence
    review_status: ClaimReviewStatus
    translation_dependent: bool
    supports: tuple[ClaimEvidence, ...]
    qualifies: tuple[ClaimEvidence, ...]
    conflicts: tuple[ClaimEvidence, ...]
    context: tuple[ClaimEvidence, ...]
    limitations: tuple[str, ...]
    publication_ready: bool


class PublicationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    allowed: bool
    reasons: tuple[str, ...]
    checked_at: str


class ClaimTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim: ClaimRecord
    evidence_chain: tuple[dict[str, object], ...]
