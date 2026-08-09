from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from sourcecut_api.models.journal import AuthorId
from sourcecut_api.models.observation import ObservationCategory

SupportLevel = Literal["HIGH", "SINGLE_SOURCE"]


class HistoricalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    passage_id: str
    entry_id: str
    source_id: str
    author_id: AuthorId
    author_display_name: str
    entry_date: date
    category: ObservationCategory
    canonical_term: str
    normalized_description: str
    explicit: bool
    source_quote: str
    source_start: Annotated[int, Field(ge=0)]
    source_end: Annotated[int, Field(gt=0)]
    passage_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    passage_text: str


class EvidenceGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_term: str
    support_level: SupportLevel
    authors: tuple[AuthorId, ...]
    evidence: tuple[HistoricalEvidence, ...]
