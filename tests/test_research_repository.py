from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from sourcecut_api.repositories.research import (
    EVENT_INSERT_SETTINGS,
    SESSION_INSERT_SETTINGS,
    ResearchEventRepository,
)


class FakeClient:
    def __init__(self) -> None:
        self.sessions: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.settings: list[dict[str, int]] = []

    def insert(
        self,
        table: str,
        rows: list[list[object]],
        *,
        column_names: list[str],
        settings: dict[str, int],
    ) -> None:
        target = self.sessions if table == "research_sessions" else self.events
        target.extend(dict(zip(column_names, row, strict=True)) for row in rows)
        self.settings.append(settings)

    def query(self, query: str, parameters: dict[str, object]) -> SimpleNamespace:
        if "FROM research_sessions FINAL" in query:
            matches = [
                row
                for row in self.sessions
                if row["session_id"] == parameters["session_id"]
            ]
            matches.sort(key=lambda row: row["updated_at"], reverse=True)
            rows = [
                tuple(
                    row[column]
                    for column in (
                        "session_id",
                        "status",
                        "prompt",
                        "board_json",
                        "error",
                        "created_at",
                        "updated_at",
                    )
                )
                for row in matches[:1]
            ]
        else:
            cursor = (parameters["occurred_at"], parameters["event_id"])
            matches = [
                row
                for row in self.events
                if row["session_id"] == parameters["session_id"]
                and (row["occurred_at"], row["event_id"]) > cursor
            ]
            matches.sort(key=lambda row: (row["occurred_at"], row["event_id"]))
            rows = [
                tuple(
                    row[column]
                    for column in (
                        "event_id",
                        "session_id",
                        "event_type",
                        "stage",
                        "status",
                        "message",
                        "payload_json",
                        "duration_ms",
                        "occurred_at",
                    )
                )
                for row in matches[: int(parameters["limit"])]
            ]
        return SimpleNamespace(result_rows=rows)


def test_session_upsert_is_durable_and_read_with_final() -> None:
    client = FakeClient()
    repository = ResearchEventRepository(client)  # type: ignore[arg-type]
    created_at = datetime(2026, 8, 11, tzinfo=UTC)

    repository.save_session(
        session_id="session-1",
        status="queued",
        prompt="Research the Bitterroot crossing",
        created_at=created_at,
    )
    repository.save_session(
        session_id="session-1",
        status="complete",
        prompt="Research the Bitterroot crossing",
        board_json='{"title":"Board"}',
        created_at=created_at,
    )

    restored = repository.get_session("session-1")
    assert restored is not None
    assert restored.status == "complete"
    assert restored.board_json == '{"title":"Board"}'
    assert client.settings[:2] == [SESSION_INSERT_SETTINGS, SESSION_INSERT_SETTINGS]


def test_events_are_fire_and_forget_and_tail_from_cursor() -> None:
    client = FakeClient()
    repository = ResearchEventRepository(client)  # type: ignore[arg-type]

    first = repository.record(
        session_id="session-1",
        event_type="mcp_tool_call",
        stage="evidence",
        status="complete",
        message="ClickHouse MCP returned rows.",
        payload={"row_count": 2, "sql": "SELECT redacted"},
        duration_ms=11,
    )
    second = repository.record(
        session_id="session-1",
        event_type="fallback",
        stage="evidence",
        status="active",
        message="Passage fallback activated.",
    )

    assert repository.list_events("session-1") == (first, second)
    assert repository.list_events(
        "session-1", after=(first.occurred_at, first.event_id)
    ) == (second,)
    assert client.settings == [EVENT_INSERT_SETTINGS, EVENT_INSERT_SETTINGS]
