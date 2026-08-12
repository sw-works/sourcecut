from __future__ import annotations

import json
from pathlib import Path

from sourcecut_api.models.classical_text import TextUnit
from sourcecut_api.models.narrative import (
    EventPassage,
    NarrativeEvent,
    NarrativeRelease,
    SpeechRecord,
)


class NarrativeReleaseError(ValueError):
    pass


def load_narrative_release(
    path: Path,
    text_units: tuple[TextUnit, ...],
) -> NarrativeRelease:
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = tuple(NarrativeEvent.model_validate(item) for item in payload["events"])
    speeches = tuple(SpeechRecord.model_validate(item) for item in payload["speeches"])
    release_id = str(payload["release_id"])
    passages = tuple(_event_passage(event) for event in events)
    release = NarrativeRelease(
        release_id=release_id,
        release_version=str(payload["release_version"]),
        curator=str(payload["curator"]),
        source_version_id=str(payload["source_version_id"]),
        events=events,
        passages=passages,
        speeches=speeches,
    )
    validate_narrative_release(release, text_units)
    return release


def validate_narrative_release(
    release: NarrativeRelease,
    text_units: tuple[TextUnit, ...],
) -> None:
    event_ids = {event.event_id for event in release.events}
    if len(event_ids) != len(release.events):
        raise NarrativeReleaseError("Narrative release has duplicate event IDs")
    covered_books = {passage.book for passage in release.passages}
    if covered_books != set(range(1, 25)):
        raise NarrativeReleaseError(
            f"Narrative release must cover books 1–24; found {sorted(covered_books)}"
        )
    available = {(unit.book, unit.line_start) for unit in text_units}
    for passage in release.passages:
        if (passage.book, passage.line_start) not in available:
            raise NarrativeReleaseError(
                f"Event passage starts at a missing source line: {passage.event_passage_id}"
            )
        if not any(
            unit.book == passage.book and unit.line_start <= passage.line_end <= unit.line_end
            for unit in text_units
        ):
            raise NarrativeReleaseError(
                f"Event passage ends at a missing source line: {passage.event_passage_id}"
            )
    for event in release.events:
        if event.parent_event_id and event.parent_event_id not in event_ids:
            raise NarrativeReleaseError(f"Unknown parent event: {event.parent_event_id}")
    for speech in release.speeches:
        if (speech.book, speech.line_start) not in available:
            raise NarrativeReleaseError(f"Speech starts at a missing line: {speech.speech_id}")
        if not any(
            unit.book == speech.book and unit.line_start <= speech.line_end <= unit.line_end
            for unit in text_units
        ):
            raise NarrativeReleaseError(f"Speech ends at a missing line: {speech.speech_id}")
    embedded_books = {
        passage.book
        for passage in release.passages
        if passage.relationship == "narrated" and 9 <= passage.book <= 12
    }
    if embedded_books != {9, 10, 11, 12}:
        raise NarrativeReleaseError("Books 9–12 must be modeled as embedded narration")
    required_types = {"memory", "prophecy", "lying_tale", "reported_story"}
    found_types = {event.event_type for event in release.events}
    if not required_types <= found_types:
        raise NarrativeReleaseError("Narrative release lacks required embedded story types")


def _event_passage(event: NarrativeEvent) -> EventPassage:
    book = event.reading_order_start // 100_000
    line_start = event.reading_order_start % 100_000
    line_end = event.reading_order_end % 100_000
    if event.event_type == "memory":
        relationship = "recalled"
    elif event.event_type == "prophecy":
        relationship = "prophesied"
    elif event.narrative_level.startswith("embedded") or event.narrative_level.startswith(
        "doubly_embedded"
    ):
        relationship = "narrated"
    else:
        relationship = "occurs"
    return EventPassage(
        event_passage_id=f"event-passage:{event.event_id.removeprefix('event:')}:grc2",
        event_id=event.event_id,
        book=book,
        line_start=line_start,
        line_end=line_end,
        relationship=relationship,
    )
