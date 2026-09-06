from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sourcecut_api.main import DEFAULT_PROMPT, create_app
from sourcecut_api.models import ResearchBoard
from sourcecut_api.repositories import StoredResearchEvent, StoredResearchSession


class FakeResearchRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, StoredResearchSession] = {}
        self.events: list[StoredResearchEvent] = []

    def save_session(self, **values: Any) -> StoredResearchSession:
        stored = StoredResearchSession(
            session_id=values["session_id"],
            status=values["status"],
            prompt=values["prompt"],
            board_json=values.get("board_json", ""),
            error=values.get("error", ""),
            created_at=values["created_at"],
            updated_at=datetime.now(UTC),
        )
        self.sessions[stored.session_id] = stored
        return stored

    def get_session(self, session_id: str) -> StoredResearchSession | None:
        return self.sessions.get(session_id)

    def record(self, **values: Any) -> StoredResearchEvent:
        event = StoredResearchEvent(
            event_id=f"event-{len(self.events) + 1}",
            session_id=values["session_id"],
            event_type=values["event_type"],
            stage=values["stage"],
            status=values["status"],
            message=values["message"],
            payload=values.get("payload") or {},
            duration_ms=values.get("duration_ms", 0),
            occurred_at=datetime.now(UTC),
        )
        self.events.append(event)
        return event

    def list_events(
        self,
        session_id: str,
        *,
        after: datetime | None = None,
        limit: int = 200,
    ) -> tuple[StoredResearchEvent, ...]:
        events = [event for event in self.events if event.session_id == session_id]
        if after is not None:
            events = [event for event in events if event.occurred_at >= after]
        return tuple(events[:limit])


class FakeBoardService:
    def __init__(self) -> None:
        self.event_sink = None

    async def build_board(self, prompt: str) -> ResearchBoard:
        if self.event_sink is not None:
            self.event_sink(
                "mcp_tool_call",
                "evidence",
                "complete",
                "ClickHouse MCP returned 2 row(s).",
                {"tool": "run_query", "row_count": 2},
                7,
            )
        return ResearchBoard(
            prompt=prompt,
            title="Crossing the Bitterroots — September 1805",
            summary="Evidence-backed test board.",
            evidence_matrix=(),
            sections=(),
            reviewed_assets=(),
            warnings=(),
            sources_used=("Library of Congress",),
        )


class FakeAssetMcp:
    def __init__(self, thumbnail_path: str) -> None:
        self.thumbnail_path = thumbnail_path

    async def get_asset(self, asset_id: str) -> dict[str, Any]:
        if asset_id != "loc:map":
            return {"status": "not_found", "asset_id": asset_id}
        return {
            "status": "found",
            "asset": {
                "asset_id": asset_id,
                "provider": "Library of Congress",
                "title": "Expedition route map",
                "rights_status": "public_domain",
                "thumbnail_path": self.thumbnail_path,
            },
        }


def test_research_session_streams_timeline_and_returns_board() -> None:
    app = create_app(session_repository=FakeResearchRepository())
    app.state.service_factory = FakeBoardService

    with TestClient(app) as client:
        started = client.post(
            "/api/research",
            json={"query": DEFAULT_PROMPT, "public_domain_only": True},
        )
        assert started.status_code == 202
        session_id = started.json()["session_id"]

        for _ in range(50):
            result = client.get(f"/api/research/{session_id}").json()
            if result["status"] == "complete":
                break
            time.sleep(0.01)

        assert result["status"] == "complete"
        assert result["board"]["title"].startswith("Crossing the Bitterroots")
        with client.stream("GET", f"/api/research/{session_id}/events") as response:
            stream = "".join(response.iter_text())
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "ClickHouse MCP" in stream
        assert '"event_type":"mcp_tool_call"' in stream
        assert '"row_count":2' in stream
        assert 'event: done' in stream


def test_unknown_session_is_404() -> None:
    with TestClient(create_app(session_repository=FakeResearchRepository())) as client:
        response = client.get("/api/research/not-found")

    assert response.status_code == 404
    assert response.json()["detail"] == "Research session was not found"


def test_top_level_asset_lookup_and_thumbnail_are_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    thumbnail = Path("data/archive-cache/loc/thumbnails/map.jpg")
    thumbnail.parent.mkdir(parents=True)
    thumbnail.write_bytes(b"jpeg")
    app = create_app(session_repository=FakeResearchRepository())
    app.state.mcp_client_factory = lambda: FakeAssetMcp(str(thumbnail))

    with TestClient(app) as client:
        asset = client.get("/api/assets/loc:map")
        image = client.get("/api/assets/loc:map/thumbnail")
        missing = client.get("/api/assets/loc:missing")
        invalid = client.get("/api/assets/not%20safe")

    assert asset.status_code == 200
    assert asset.json()["provider"] == "Library of Congress"
    assert asset.json()["thumbnail_url"] == "/api/assets/loc:map/thumbnail"
    assert image.content == b"jpeg"
    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_second_api_instance_reads_completed_session_from_shared_store() -> None:
    repository = FakeResearchRepository()
    first_app = create_app(session_repository=repository)
    first_app.state.service_factory = FakeBoardService

    with TestClient(first_app) as first:
        started = first.post(
            "/api/research",
            json={"query": DEFAULT_PROMPT, "public_domain_only": True},
        ).json()
        for _ in range(50):
            if first.get(f"/api/research/{started['session_id']}").json()["status"] == "complete":
                break
            time.sleep(0.01)

    with TestClient(create_app(session_repository=repository)) as second:
        restored = second.get(f"/api/research/{started['session_id']}")

    assert restored.status_code == 200
    assert restored.json()["status"] == "complete"
    assert restored.json()["board"]["title"].startswith("Crossing the Bitterroots")


def test_research_request_requires_meaningful_query() -> None:
    with TestClient(create_app(session_repository=FakeResearchRepository())) as client:
        response = client.post(
            "/api/research", json={"query": "short", "public_domain_only": True}
        )

    assert response.status_code == 422


def test_agent_research_streams_hook_events_and_the_final_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ADK path reports on the same stream the board path uses.

    `run_research_session` stands in for a real ADK run so this needs no Gemini
    credential; what it exercises is that whatever the hooks emit reaches the
    session timeline, and that the prose answer arrives as a terminal event.
    """

    async def fake_run(
        question: str,
        session_id: str,
        *,
        pipeline: bool,
        sink: object,
        user_id: str = "sourcecut",
    ) -> str:
        del question, session_id, user_id
        assert pipeline is True
        assert callable(sink)
        sink("stage_started", "sourcecut_planner", "active", "Planner started.", {}, 0)
        sink(
            "tool_blocked",
            "sourcecut_evidence",
            "failed",
            "run_query was refused: LIMIT too large",
            {"tool": "run_query"},
            12,
        )
        return "Two authors record snow on 1805-09-16."

    monkeypatch.setattr("sourcecut_api.main.run_research_session", fake_run)
    app = create_app(session_repository=FakeResearchRepository())

    with TestClient(app) as client:
        started = client.post(
            "/api/research/agent",
            json={"query": DEFAULT_PROMPT, "public_domain_only": True},
        )
        assert started.status_code == 202
        session_id = started.json()["session_id"]
        assert started.json()["events_url"] == f"/api/research/{session_id}/events"

        for _ in range(50):
            result = client.get(f"/api/research/{session_id}").json()
            if result["status"] == "complete":
                break
            time.sleep(0.01)

        assert result["status"] == "complete"
        # The ADK path answers in prose; there is no board to show.
        assert result["board"] is None
        with client.stream("GET", f"/api/research/{session_id}/events") as response:
            stream = "".join(response.iter_text())

    assert '"event_type":"stage_started"' in stream
    assert '"event_type":"tool_blocked"' in stream
    assert "Two authors record snow" in stream
    assert "event: done" in stream
