from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conftest import FakeClickHouseClient
from fastapi.testclient import TestClient

from pipelines.classics import load_narrative_release
from sourcecut_api.main import create_app
from sourcecut_api.models.classical_text import TextUnit
from sourcecut_api.repositories import ClickHouseNarrativeRepository

ROOT = Path(__file__).parents[1]
RELEASE_PATH = ROOT / "data" / "reference" / "odyssey_narrative.json"


def _units() -> tuple[TextUnit, ...]:
    payload = json.loads(RELEASE_PATH.read_text())
    lines = {
        (int(item["reading_order_start"]) // 100_000, int(item["reading_order_start"]) % 100_000)
        for item in payload["events"]
    }
    lines |= {
        (int(item["reading_order_end"]) // 100_000, int(item["reading_order_end"]) % 100_000)
        for item in payload["events"]
    }
    lines |= {(int(item["book"]), int(item["line_start"])) for item in payload["speeches"]}
    lines |= {(int(item["book"]), int(item["line_end"])) for item in payload["speeches"]}
    return tuple(
        TextUnit(
            text_unit_id=f"text-unit:odyssey-perseus-grc2:{book}:{line}-{line}",
            version_id="odyssey-perseus-grc2",
            work_id="odyssey",
            book=book,
            line_start=line,
            line_end=line,
            citation=f"Od. {book}.{line}",
            source_line_start=line,
            source_line_end=line,
            unit_index=line,
            cts_urn=f"urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:{book}.{line}",
            original_text="source",
            normalized_text="source",
            text_sha256="0" * 64,
            source_document_id="raw:grc2",
            parser_version="test-v1",
        )
        for book, line in sorted(lines)
    )


def test_curated_narrative_covers_all_books_and_separates_orders() -> None:
    release = load_narrative_release(RELEASE_PATH, _units())
    assert {item.book for item in release.passages} == set(range(1, 25))
    cyclops = next(item for item in release.events if item.event_id == "event:cyclops")
    calypso = next(item for item in release.events if item.event_id == "event:calypso-departure")
    assert cyclops.reading_order_start > calypso.reading_order_start
    assert cyclops.story_order_start < calypso.story_order_start
    assert {p.book for p in release.passages if p.relationship == "narrated"} >= {9, 10, 11, 12}


def test_narrative_repository_is_idempotent() -> None:
    release = load_narrative_release(RELEASE_PATH, _units())
    client = FakeClickHouseClient("corpus")
    repository = ClickHouseNarrativeRepository(client)  # type: ignore[arg-type]
    first = repository.load(release)
    second = repository.load(release)
    assert first.events_inserted == len(release.events)
    assert first.passages_inserted == len(release.passages)
    assert first.speeches_inserted == len(release.speeches)
    assert second.events_inserted == second.passages_inserted == second.speeches_inserted == 0


class FakeNarrativeMcp:
    async def get_odyssey_timeline(self, **kwargs: Any) -> list[dict[str, Any]]:
        mode = kwargs["mode"]
        rows = [
            _row("event:cyclops", 900105, "103"),
            _row("event:calypso-departure", 500001, "200"),
        ]
        key = "reading_order_start" if mode == "reading" else "story_order_start"
        return sorted(rows, key=lambda row: row[key])

    async def get_odyssey_event(self, event_id: str) -> list[dict[str, Any]]:
        return [_row(event_id, 900105, "103")]

    async def get_odyssey_speeches(
        self, speakers: list[str], books: list[int]
    ) -> list[dict[str, Any]]:
        del speakers, books
        return [
            {
                "speech_id": "speech:apologia-9",
                "speaker_entity_id": "odysseus",
                "addressee_entity_ids": ["phaeacians"],
                "audience_entity_ids": ["phaeacian-court"],
                "narrator_entity_id": "odysseus",
                "narrative_level": "embedded_first_person",
                "book": 9,
                "line_start": 1,
                "line_end": 38,
                "speech_type": "direct",
            }
        ]


def _row(event_id: str, reading: int, story: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "title": "Event",
        "summary": "Summary",
        "event_type": "embedded_wandering",
        "reading_order_start": reading,
        "reading_order_end": reading + 10,
        "story_order_start": story,
        "story_order_end": story,
        "duration_value": None,
        "duration_unit": "unknown",
        "duration_certainty": "unknown",
        "duration_source_note": "",
        "narrative_level": "embedded_first_person",
        "narrator_entity_id": "odysseus",
        "participant_entity_ids": ["odysseus"],
        "place_ids": ["cyclopes-land"],
        "theme_ids": ["identity"],
        "parent_event_id": None,
        "passages": [["odyssey-perseus-grc2", 9, 105, 115, "narrated", "PRIMARY_GREEK_EXPLICIT"]],
    }


def test_narrative_api_orders_and_exposes_exact_passages() -> None:
    app = create_app()
    app.state.mcp_client_factory = FakeNarrativeMcp
    client = TestClient(app)
    reading = client.get("/api/v1/timelines/odyssey?mode=reading")
    story = client.get("/api/v1/timelines/odyssey?mode=story")
    event = client.get("/api/v1/events/event:cyclops")
    speeches = client.get("/api/v1/speeches?speakers=odysseus&books=9")
    assert (
        reading.status_code == story.status_code == event.status_code == speeches.status_code == 200
    )
    assert reading.json()["events"][0]["event_id"] == "event:calypso-departure"
    assert story.json()["events"][0]["event_id"] == "event:cyclops"
    assert event.json()["passages"][0]["relationship"] == "narrated"
    assert speeches.json()[0]["addressee_entity_ids"] == ["phaeacians"]
