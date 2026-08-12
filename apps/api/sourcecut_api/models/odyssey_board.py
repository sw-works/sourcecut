from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoardItemKind(StrEnum):
    CLAIM = "claim"
    PASSAGE = "passage"
    EVENT = "event"
    MAP_VIEW = "map_view"
    ENTITY = "entity"
    ASSET = "asset"
    SAVED_SEARCH = "saved_search"


class BoardItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    kind: BoardItemKind
    reference_id: Annotated[str, Field(min_length=1, max_length=500)]
    label: Annotated[str, Field(min_length=1, max_length=300)]
    citation: str = ""
    rights_status: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OdysseyBoardSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    title: Annotated[str, Field(min_length=1, max_length=160)]
    generated_text: Annotated[str, Field(max_length=20_000)] = ""
    user_notes: Annotated[str, Field(max_length=20_000)] = ""
    items: tuple[BoardItem, ...] = ()
    warnings: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    hidden_generated_text: bool = False


class BoardReleasePins(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_manifest_id: str
    corpus_revision: str
    annotation_release_ids: tuple[str, ...] = ()
    active_versions: tuple[str, ...] = ()
    active_hypotheses: tuple[str, ...] = ("textual-sequence",)


class BoardTraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    event_type: Literal["agent", "mcp", "system"]
    stage: str
    message: str
    occurred_at: datetime
    tool_name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class OdysseyBoard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    board_id: str
    revision_id: str
    corpus_id: Literal["odyssey"] = "odyssey"
    title: Annotated[str, Field(min_length=1, max_length=240)]
    question: Annotated[str, Field(max_length=2_000)] = ""
    summary: Annotated[str, Field(max_length=20_000)] = ""
    sections: tuple[OdysseyBoardSection, ...]
    release_pins: BoardReleasePins
    warnings: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    unsupported_questions: tuple[str, ...] = ()
    agent_trace: tuple[BoardTraceEvent, ...] = ()
    source_session_id: str = ""
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def unique_sections_and_items(self) -> OdysseyBoard:
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("board section identifiers must be unique")
        item_ids = [item.item_id for section in self.sections for item in section.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("board item identifiers must be unique")
        return self


class BoardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=240)]
    question: Annotated[str, Field(max_length=2_000)] = ""
    summary: Annotated[str, Field(max_length=20_000)] = ""
    sections: tuple[OdysseyBoardSection, ...] = ()
    release_pins: BoardReleasePins
    warnings: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    unsupported_questions: tuple[str, ...] = ()
    agent_trace: tuple[BoardTraceEvent, ...] = ()
    source_session_id: str = ""


class BoardPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: str
    title: Annotated[str | None, Field(min_length=1, max_length=240)] = None
    question: Annotated[str | None, Field(max_length=2_000)] = None
    summary: Annotated[str | None, Field(max_length=20_000)] = None
    sections: tuple[OdysseyBoardSection, ...] | None = None
    warnings: tuple[str, ...] | None = None
    conflicts: tuple[str, ...] | None = None
    unsupported_questions: tuple[str, ...] | None = None
    actor: Annotated[str, Field(min_length=1, max_length=120)] = "public-user"


class SectionRegeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: str
    generated_text: Annotated[str, Field(min_length=1, max_length=20_000)]
    warnings: tuple[str, ...] = ()
    trace: tuple[BoardTraceEvent, ...] = ()
    actor: Annotated[str, Field(min_length=1, max_length=120)] = "research-agent"


class BoardRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    revision_id: str
    board_id: str
    parent_revision_id: str
    revision_kind: Literal["current", "candidate", "snapshot", "duplicate"]
    changed_fields: tuple[str, ...]
    actor: str
    release_pins: BoardReleasePins
    document: OdysseyBoard
    created_at: datetime


class SnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: str
    actor: Annotated[str, Field(min_length=1, max_length=120)] = "public-user"
