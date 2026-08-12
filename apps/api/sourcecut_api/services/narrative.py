from __future__ import annotations

from decimal import Decimal

from sourcecut_api.models.narrative import SpeechView, TimelineEventView, TimelineResponse


def build_timeline_response(mode: str, rows: list[dict[str, object]]) -> TimelineResponse:
    events = tuple(_event(row) for row in rows)
    return TimelineResponse(
        mode=mode,  # type: ignore[arg-type]
        events=events,
        coverage_books=tuple(sorted({int(p["book"]) for e in events for p in e.passages})),
    )


def build_speeches(rows: list[dict[str, object]]) -> tuple[SpeechView, ...]:
    return tuple(SpeechView.model_validate(row) for row in rows)


def _event(row: dict[str, object]) -> TimelineEventView:
    passages = []
    for passage in row.get("passages", []) or []:
        if isinstance(passage, dict):
            passages.append(passage)
        else:
            values = list(passage)
            passages.append(
                dict(
                    zip(
                        (
                            "version_id",
                            "book",
                            "line_start",
                            "line_end",
                            "relationship",
                            "evidence_class",
                        ),
                        values,
                        strict=True,
                    )
                )
            )
    return TimelineEventView(
        event_id=str(row["event_id"]),
        title=str(row["title"]),
        summary=str(row["summary"]),
        event_type=str(row["event_type"]),
        reading_order_start=int(row["reading_order_start"]),
        reading_order_end=int(row["reading_order_end"]),
        story_order_start=Decimal(str(row["story_order_start"])),
        story_order_end=Decimal(str(row["story_order_end"])),
        duration_value=float(row["duration_value"])
        if row.get("duration_value") is not None
        else None,
        duration_unit=str(row["duration_unit"]),
        duration_certainty=str(row["duration_certainty"]),
        duration_source_note=str(row["duration_source_note"]),
        narrative_level=str(row["narrative_level"]),
        narrator_entity_id=str(row["narrator_entity_id"]),
        participant_entity_ids=tuple(str(x) for x in row.get("participant_entity_ids", []) or []),
        place_ids=tuple(str(x) for x in row.get("place_ids", []) or []),
        theme_ids=tuple(str(x) for x in row.get("theme_ids", []) or []),
        parent_event_id=str(row["parent_event_id"]) if row.get("parent_event_id") else None,
        passages=tuple(passages),
    )
