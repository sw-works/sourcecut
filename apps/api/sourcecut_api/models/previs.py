from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShotType(StrEnum):
    ESTABLISHING = "establishing_shot"
    TRAVEL = "travel_shot"
    CAMP = "camp_scene"
    LANDSCAPE = "landscape_plate"


class EvidenceStrictness(StrEnum):
    STRICT = "strict"
    INTERPRETIVE = "interpretive"


class PrevisJobStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"


class ConsistencyLabel(StrEnum):
    SUPPORTED = "supported"
    INTERPRETIVE = "interpretive"
    UNSUPPORTED = "unsupported"


class ConsistencyResult(StrEnum):
    CONSISTENT = "consistent"
    NEEDS_REVIEW = "needs_review"
    UNSUPPORTED = "unsupported"


class SupportedDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detail: Annotated[str, Field(min_length=2, max_length=300)]
    observation_ids: Annotated[tuple[str, ...], Field(min_length=1)]
    passage_ids: Annotated[tuple[str, ...], Field(min_length=1)]


class ShotBriefContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    purpose: Annotated[str, Field(min_length=2, max_length=300)]
    setting: Annotated[str, Field(min_length=2, max_length=500)]
    action: Annotated[str, Field(min_length=2, max_length=500)]
    composition: Annotated[str, Field(min_length=2, max_length=500)]
    camera_motion: Annotated[str, Field(min_length=2, max_length=300)]
    ambience: Annotated[str, Field(min_length=2, max_length=300)]
    supported_details: Annotated[tuple[SupportedDetail, ...], Field(min_length=1)]
    interpretive_additions: tuple[str, ...] = ()
    excluded_details: Annotated[tuple[str, ...], Field(min_length=1)]
    positive_prompt: Annotated[str, Field(min_length=20, max_length=2_000)]
    negative_prompt: Annotated[str, Field(min_length=2, max_length=1_000)]

    @model_validator(mode="after")
    def negative_prompt_uses_noun_phrases(self) -> ShotBriefContent:
        lowered = self.negative_prompt.casefold()
        if "do not" in lowered or "don't" in lowered:
            raise ValueError("negative_prompt must use noun phrases, not instructions")
        return self


class ShotBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shot_brief_id: str
    research_session_id: str
    board_section_id: str
    board_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    shot_type: ShotType
    strictness: EvidenceStrictness
    duration_seconds: Annotated[int, Field(ge=1, le=8)]
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    generate_audio: bool = False
    reference_asset_ids: tuple[str, ...] = ()
    producer_model: str
    prompt_version: str
    created_at: datetime
    content: ShotBriefContent

    @model_validator(mode="after")
    def strict_mode_has_no_interpretive_additions(self) -> ShotBrief:
        if (
            self.strictness is EvidenceStrictness.STRICT
            and self.content.interpretive_additions
        ):
            raise ValueError("strict shot briefs cannot contain interpretive additions")
        if self.generate_audio:
            raise ValueError("audio generation is outside the first previs slice")
        return self


class PrevisJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    shot_brief_id: str
    status: PrevisJobStatus
    parent_job_id: str | None = None
    provider: str = "google"
    model: str
    provider_operation_name: str = ""
    request_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    estimated_cost_usd: Annotated[float, Field(ge=0)]
    generation_count: Annotated[int, Field(ge=1)]
    created_at: datetime
    updated_at: datetime
    output_uri: str = ""
    safe_error: str = ""


class ConsistencyFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: ConsistencyLabel
    visible_detail: Annotated[str, Field(min_length=2, max_length=500)]
    approximate_time_range: Annotated[str, Field(min_length=1, max_length=80)]
    severity: Literal["info", "warning", "critical"]
    rationale: Annotated[str, Field(min_length=2, max_length=700)]
    observation_ids: tuple[str, ...] = ()
    passage_ids: tuple[str, ...] = ()


class ConsistencyReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    overall_result: ConsistencyResult
    findings: tuple[ConsistencyFinding, ...]
    correction_instructions: tuple[str, ...] = ()
    critic_model: str
    prompt_version: str
    reviewed_at: datetime


class CorrectionOutcome(BaseModel):
    """Deterministic comparison of a corrected clip against its parent review.

    Closes the producer/critic loop: the critic reviews the corrected clip
    exactly as it reviewed the original, and this compares the two reports so
    a viewer can see which flagged details the correction actually removed.
    No model call is involved in the comparison.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_job_id: str
    resolved: tuple[str, ...] = ()
    persisting: tuple[str, ...] = ()
    introduced: tuple[str, ...] = ()

    @property
    def fully_resolved(self) -> bool:
        return not self.persisting and not self.introduced


class ShotBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    board_section_title: Annotated[str, Field(min_length=2, max_length=200)]
    shot_type: ShotType = ShotType.ESTABLISHING
    strictness: EvidenceStrictness = EvidenceStrictness.STRICT
    duration_seconds: Annotated[int, Field(ge=1, le=8)] = 8
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    reference_asset_ids: tuple[str, ...] = ()


class GenerationApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    brief_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class CorrectionApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    job_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ShotBriefEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    brief: ShotBrief
    brief_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    estimated_cost_usd: float | None
    can_generate: bool
    blockers: tuple[str, ...] = ()


class PrevisJobEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job: PrevisJob
    job_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    report: ConsistencyReport | None = None
    correction_outcome: CorrectionOutcome | None = None
    disclosure: str = "AI-generated previsualization — not historical evidence"
    video_url: str = ""
