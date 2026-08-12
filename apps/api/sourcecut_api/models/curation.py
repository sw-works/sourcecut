from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CurationTarget(StrEnum):
    ENTITY = "entity"
    EVENT = "event"
    SPEECH = "speech"
    MORPHOLOGY = "morphology"
    ALIGNMENT = "alignment"
    CLAIM = "claim"
    PLACE_HYPOTHESIS = "place_hypothesis"
    LICENSE = "license"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    TRUSTED = "trusted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class CurationProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: CurationTarget
    target_id: Annotated[str, Field(min_length=1, max_length=500)]
    base_revision_id: Annotated[str, Field(min_length=1, max_length=200)]
    proposed_changes: dict[str, Any] = Field(min_length=1, max_length=50)
    rationale: Annotated[str, Field(min_length=5, max_length=4_000)]
    citations: tuple[Annotated[str, Field(min_length=1, max_length=500)], ...]
    proposer_id: Annotated[str, Field(min_length=1, max_length=120)]


class CurationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: Annotated[int, Field(ge=1)]
    status: Literal["reviewed", "trusted", "rejected", "superseded"]
    reviewer_id: Annotated[str, Field(min_length=1, max_length=120)]
    review_note: Annotated[str, Field(min_length=5, max_length=4_000)]


class CurationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str
    revision: int
    target_type: CurationTarget
    target_id: str
    base_revision_id: str
    proposed_changes: dict[str, Any]
    rationale: str
    citations: tuple[str, ...]
    status: ReviewStatus
    proposer_id: str
    reviewer_id: str = ""
    review_note: str = ""
    created_at: datetime
    updated_at: datetime


class CurationAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_id: str
    action: str
    actor_id: str
    target_type: str
    target_id: str
    before_revision: str
    after_revision: str
    detail: dict[str, Any]
    occurred_at: datetime


class ImportRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    import_kind: Literal["corpus", "gazetteer", "media"]
    upstream_revision: Annotated[str, Field(min_length=1, max_length=200)]
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    actor_id: Annotated[str, Field(min_length=1, max_length=120)]


class ImportRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    import_run_id: str
    idempotency_key: str
    import_kind: str
    upstream_revision: str
    manifest_sha256: str
    status: Literal["registered", "complete", "quarantined"]
    created_at: datetime


class ReleaseManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    records: dict[str, Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]]


class ReleaseComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    added: tuple[str, ...]
    changed: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged_count: int


class CorpusReleaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=200)]
    upstream_revision: Annotated[str, Field(min_length=1, max_length=200)]
    source_version_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...]
    curation_record_ids: tuple[str, ...]
    license_record_ids: tuple[str, ...]
    import_run_ids: tuple[str, ...]
    comparison: ReleaseComparison
    actor_id: Annotated[str, Field(min_length=1, max_length=120)]

    @model_validator(mode="after")
    def licenses_are_part_of_release(self) -> CorpusReleaseCreate:
        if not set(self.license_record_ids) <= set(self.curation_record_ids):
            raise ValueError("license records must be included in curation_record_ids")
        return self


class CorpusRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    label: str
    upstream_revision: str
    source_version_ids: tuple[str, ...]
    curation_record_ids: tuple[str, ...]
    license_record_ids: tuple[str, ...]
    import_run_ids: tuple[str, ...]
    comparison: ReleaseComparison
    status: Literal["candidate", "active", "superseded"]
    created_by: str
    promoted_by: str = ""
    created_at: datetime
    promoted_at: datetime | None = None


class ReleasePromotion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: Annotated[str, Field(min_length=1, max_length=120)]
    note: Annotated[str, Field(min_length=5, max_length=2_000)]


class ReleaseRollback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: str
    actor_id: Annotated[str, Field(min_length=1, max_length=120)]
    reason: Annotated[str, Field(min_length=5, max_length=2_000)]


class DerivedRebuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: Literal["entities", "events", "speeches", "morphology", "alignments", "claims", "places"]
    source_version_ids: tuple[Annotated[str, Field(min_length=1, max_length=300)], ...]
    actor_id: Annotated[str, Field(min_length=1, max_length=120)]


class DerivedRebuild(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rebuild_id: str
    layer: str
    source_version_ids: tuple[str, ...]
    source_mutations: Literal[0] = 0
    status: Literal["queued"] = "queued"
    created_at: datetime


class CoverageDashboard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    by_target: dict[str, int]
    by_status: dict[str, int]
    trusted_percent: float
    license_records_trusted: int
    unresolved_records: int
    import_runs: int
    active_release_id: str
    generated_at: datetime
