from __future__ import annotations

import time

from fastapi.testclient import TestClient

from sourcecut_api.main import DEFAULT_PROMPT, create_app
from sourcecut_api.models import ResearchBoard


class FakeBoardService:
    async def build_board(self, prompt: str) -> ResearchBoard:
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


def test_research_session_streams_timeline_and_returns_board() -> None:
    app = create_app()
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
        assert 'event: done' in stream


def test_unknown_session_is_404() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/research/not-found")

    assert response.status_code == 404
    assert response.json()["detail"] == "Research session was not found"


def test_research_request_requires_meaningful_query() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/research", json={"query": "short", "public_domain_only": True}
        )

    assert response.status_code == 422
