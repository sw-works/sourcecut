from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NarrativeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    work_id: str = "odyssey"
    title: str
    summary: str
    event_type: str
    reading_order_start: Annotated[int, Field(ge=1)]
    reading_order_end: Annotated[int, Field(ge=1)]
    story_order_start: Decimal
    story_order_end: Decimal
    duration_value: float | None = None
    duration_unit: str = "unknown"
    duration_certainty: str = "unknown"
    duration_source_note: str = ""
    narrative_level: str
    narrator_entity_id: str
    participant_entity_ids: tuple[str, ...] = ()
    place_ids: tuple[str, ...] = ()
    theme_ids: tuple[str, ...] = ()
    parent_event_id: str | None = None
    review_status: str = "trusted"

    @model_validator(mode="after")
    def validate_orders(self) -> NarrativeEvent:
        if self.reading_order_end < self.reading_order_start:
            raise ValueError("Reading-order range is reversed")
        if self.story_order_end < self.story_order_start:
            raise ValueError("Story-order range is reversed")
        if self.duration_value is None and self.duration_certainty != "unknown":
            raise ValueError("Duration certainty requires a duration value")
        return self


class EventPassage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_passage_id: str
    event_id: str
    version_id: str = "odyssey-perseus-grc2"
    book: Annotated[int, Field(ge=1, le=24)]
    line_start: Annotated[int, Field(ge=1)]
    line_end: Annotated[int, Field(ge=1)]
    relationship: Literal["occurs", "narrated", "recalled", "prophesied", "summarized"]
    evidence_class: str = "PRIMARY_GREEK_EXPLICIT"
    review_status: str = "trusted"


class SpeechRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    speech_id: str
    work_id: str = "odyssey"
    speaker_entity_id: str
    addressee_entity_ids: tuple[str, ...] = ()
    audience_entity_ids: tuple[str, ...] = ()
    narrator_entity_id: str = "homeric-narrator"
    narrative_level: str
    book: Annotated[int, Field(ge=1, le=24)]
    line_start: Annotated[int, Field(ge=1)]
    line_end: Annotated[int, Field(ge=1)]
    speech_type: str = "direct"
    evidence_status: str = "exact_range"
    review_status: str = "trusted"


class TimelineEventView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    title: str
    summary: str
    event_type: str
    reading_order_start: int
    reading_order_end: int
    story_order_start: Decimal
    story_order_end: Decimal
    duration_value: float | None
    duration_unit: str
    duration_certainty: str
    duration_source_note: str
    narrative_level: str
    narrator_entity_id: str
    participant_entity_ids: tuple[str, ...]
    place_ids: tuple[str, ...]
    theme_ids: tuple[str, ...]
    parent_event_id: str | None
    passages: tuple[dict[str, object], ...]


class SpeechView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    speech_id: str
    speaker_entity_id: str
    addressee_entity_ids: tuple[str, ...]
    audience_entity_ids: tuple[str, ...]
    narrator_entity_id: str
    narrative_level: str
    book: int
    line_start: int
    line_end: int
    speech_type: str


class TimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["reading", "story"]
    events: tuple[TimelineEventView, ...]
    coverage_books: tuple[int, ...]
    ordering_notice: str = (
        "Story positions are curated ordinal sequence values, not historical dates."
    )


class NarrativeRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    release_version: str
    curator: str
    source_version_id: str
    events: tuple[NarrativeEvent, ...]
    passages: tuple[EventPassage, ...]
    speeches: tuple[SpeechRecord, ...]
