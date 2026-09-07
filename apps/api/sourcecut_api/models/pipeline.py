"""How far a corpus has come along the ingestion path.

The same five steps describe every corpus — acquire a text under a licence,
parse it into citable units, segment those into passages, extract observations
against exact spans, and open it to research — but each corpus answers them with
its own nouns. Lewis and Clark counts dated entries and journal observations;
the Odyssey counts lines and narrative events. The step names are shared so the
two can be read side by side; the counts are not invented to match.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class StageState(StrEnum):
    DONE = "done"
    PARTIAL = "partial"
    EMPTY = "empty"


class PipelineStage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    state: StageState
    #: What this step did for this corpus, in that corpus's own terms.
    summary: str
    #: Named counts, ready to render: ("passages", 2384).
    counts: tuple[tuple[str, int], ...] = ()
    #: The command that performs this step, when a person would run one.
    command: str = ""


class ResearchWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope_id: str
    title: str
    #: Free text: a date range for a journal, a book range for a poem.
    span: str
    captured: bool = False


class CorpusPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_id: str
    title: str
    description: str
    status: str
    display_policy: str
    licenses: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    stages: tuple[PipelineStage, ...] = ()
    windows: tuple[ResearchWindow, ...] = ()
    known_limitations: tuple[str, ...] = ()
