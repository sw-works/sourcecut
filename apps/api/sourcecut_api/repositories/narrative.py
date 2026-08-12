from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from sourcecut_api.models.narrative import NarrativeRelease

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client


class NarrativeDriftError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NarrativeLoadResult:
    events_inserted: int
    passages_inserted: int
    speeches_inserted: int


class ClickHouseNarrativeRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load(self, release: NarrativeRelease) -> NarrativeLoadResult:
        events = self._missing("narrative_events", "event_id", list(release.events))
        passages = self._missing("event_passages", "event_passage_id", list(release.passages))
        speeches = self._missing("speeches", "speech_id", list(release.speeches))
        now = datetime.now(UTC)
        self._insert(
            "narrative_events",
            [
                "event_id",
                "work_id",
                "title",
                "summary",
                "event_type",
                "reading_order_start",
                "reading_order_end",
                "story_order_start",
                "story_order_end",
                "duration_value",
                "duration_unit",
                "duration_certainty",
                "duration_source_note",
                "narrative_level",
                "narrator_entity_id",
                "participant_entity_ids",
                "place_ids",
                "theme_ids",
                "parent_event_id",
                "review_status",
                "release_id",
                "record_sha256",
                "updated_at",
            ],
            [
                [
                    item.event_id,
                    item.work_id,
                    item.title,
                    item.summary,
                    item.event_type,
                    item.reading_order_start,
                    item.reading_order_end,
                    item.story_order_start,
                    item.story_order_end,
                    item.duration_value,
                    item.duration_unit,
                    item.duration_certainty,
                    item.duration_source_note,
                    item.narrative_level,
                    item.narrator_entity_id,
                    list(item.participant_entity_ids),
                    list(item.place_ids),
                    list(item.theme_ids),
                    item.parent_event_id,
                    item.review_status,
                    release.release_id,
                    _record_hash(item),
                    now,
                ]
                for item in events
            ],
        )
        self._insert(
            "event_passages",
            [
                "event_passage_id",
                "event_id",
                "version_id",
                "book",
                "line_start",
                "line_end",
                "relationship",
                "evidence_class",
                "review_status",
                "release_id",
                "record_sha256",
                "updated_at",
            ],
            [
                [
                    item.event_passage_id,
                    item.event_id,
                    item.version_id,
                    item.book,
                    item.line_start,
                    item.line_end,
                    item.relationship,
                    item.evidence_class,
                    item.review_status,
                    release.release_id,
                    _record_hash(item),
                    now,
                ]
                for item in passages
            ],
        )
        self._insert(
            "speeches",
            [
                "speech_id",
                "work_id",
                "speaker_entity_id",
                "addressee_entity_ids",
                "audience_entity_ids",
                "narrator_entity_id",
                "narrative_level",
                "book",
                "line_start",
                "line_end",
                "speech_type",
                "evidence_status",
                "review_status",
                "release_id",
                "record_sha256",
                "updated_at",
            ],
            [
                [
                    item.speech_id,
                    item.work_id,
                    item.speaker_entity_id,
                    list(item.addressee_entity_ids),
                    list(item.audience_entity_ids),
                    item.narrator_entity_id,
                    item.narrative_level,
                    item.book,
                    item.line_start,
                    item.line_end,
                    item.speech_type,
                    item.evidence_status,
                    item.review_status,
                    release.release_id,
                    _record_hash(item),
                    now,
                ]
                for item in speeches
            ],
        )
        return NarrativeLoadResult(len(events), len(passages), len(speeches))

    def _missing(self, table: str, id_field: str, records: list[BaseModel]) -> list[BaseModel]:
        if not records:
            return []
        ids = [str(getattr(item, id_field)) for item in records]
        rows = self._client.query(
            f"SELECT {id_field}, record_sha256 FROM {table} "
            f"WHERE {id_field} IN {{ids:Array(String)}}",
            parameters={"ids": ids},
        ).result_rows
        existing = {str(row[0]): _hash_text(row[1]) for row in rows}
        missing = []
        for item in records:
            record_id = str(getattr(item, id_field))
            expected = _record_hash(item)
            if record_id not in existing:
                missing.append(item)
            elif existing[record_id] != expected:
                raise NarrativeDriftError(f"{table}.{record_id} has a different hash")
        return missing

    def _insert(self, table: str, columns: Sequence[str], rows: list[list[object]]) -> None:
        if rows:
            self._client.insert(table, rows, column_names=list(columns))


def _record_hash(item: BaseModel) -> str:
    return hashlib.sha256(item.model_dump_json().encode()).hexdigest()


def _hash_text(value: str | bytes) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else value
