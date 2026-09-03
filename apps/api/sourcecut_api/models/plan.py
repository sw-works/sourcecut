"""Typed research plans and coverage reports.

A plan is what the model is allowed to decide: which corpus window to
investigate and which production requirements to chase. Evidence resolution
stays deterministic application code (ADR-003/ADR-013), so a plan never
carries historical claims — only the shape of the investigation.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from sourcecut_api.models.observation import ObservationCategory

CoverageStatus = Literal["met", "single_source", "unmet"]

WindowDate = Annotated[int, Field(ge=18000101, le=18991231)]


class PlannedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: ObservationCategory
    title: Annotated[str, Field(min_length=2, max_length=120)]
    production_need: Annotated[str, Field(min_length=2, max_length=400)]
    search_terms: Annotated[tuple[str, ...], Field(min_length=1, max_length=12)]
    success_criteria: Annotated[str, Field(min_length=2, max_length=300)]
    minimum_authors: Annotated[int, Field(ge=1, le=3)] = 2


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_id: Annotated[str, Field(pattern=r"^[a-z0-9-]{3,64}$")]
    title: Annotated[str, Field(min_length=2, max_length=160)]
    window_start: WindowDate
    window_end: WindowDate
    rationale: Annotated[str, Field(min_length=2, max_length=600)]
    requirements: Annotated[tuple[PlannedRequirement, ...], Field(min_length=1, max_length=8)]
    planner: Annotated[str, Field(min_length=2, max_length=80)]
    prompt_version: Annotated[str, Field(min_length=2, max_length=80)]

    def with_requirements(
        self, requirements: tuple[PlannedRequirement, ...]
    ) -> ResearchPlan:
        return self.model_copy(update={"requirements": requirements})


class CoverageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str
    category: str
    status: CoverageStatus
    evidence_count: int
    author_count: int
    minimum_authors: int
    success_criteria: str


class CoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: tuple[CoverageEntry, ...]
    rounds: Annotated[int, Field(ge=1, le=5)] = 1

    @property
    def gaps(self) -> tuple[CoverageEntry, ...]:
        return tuple(entry for entry in self.entries if entry.status != "met")

    @property
    def met_count(self) -> int:
        return sum(entry.status == "met" for entry in self.entries)


class ResearchScope(BaseModel):
    """Curated corpus segment the router may select (ADR-017 reference data)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_id: Annotated[str, Field(pattern=r"^[a-z0-9-]{3,64}$")]
    title: Annotated[str, Field(min_length=2, max_length=160)]
    window_start: WindowDate
    window_end: WindowDate
    keywords: tuple[str, ...] = ()
    notes: str = ""
    default: bool = False
