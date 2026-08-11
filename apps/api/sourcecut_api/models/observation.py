from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ObservationCategory = Literal[
    "weather",
    "terrain",
    "transportation",
    "food",
    "shelter",
    "equipment",
    "person",
    "animal",
    "place",
    "health",
    "event",
]


class ObservationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: ObservationCategory
    canonical_term: Annotated[str, Field(min_length=1)]
    normalized_description: Annotated[str, Field(min_length=1)]
    explicit: bool
    source_quote: Annotated[str, Field(min_length=1)]
    source_start: Annotated[int, Field(ge=0)]
    source_end: Annotated[int, Field(ge=1)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class ObservationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observations: tuple[ObservationCandidate, ...]


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passage_id: str
    passage_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    model: str
    schema_version: str
    prompt_version: str
    idempotency_key: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    candidates: tuple[ObservationCandidate, ...]


ValidationFailureType = Literal[
    "schema_validation",
    "invalid_span_order",
    "span_out_of_bounds",
    "quote_mismatch",
    "exact_duplicate",
]


class EvidenceValidationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_index: Annotated[int, Field(ge=0)]
    failure_type: ValidationFailureType
    message: str
    raw_candidate: dict[str, object]


class EvidenceValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trusted_candidates: tuple[ObservationCandidate, ...]
    failures: tuple[EvidenceValidationFailure, ...]
