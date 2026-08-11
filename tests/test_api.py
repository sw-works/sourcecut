from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from sourcecut_api.main import DEFAULT_PROMPT, create_app
from sourcecut_api.models import (
    ConsistencyFinding,
    ConsistencyLabel,
    ConsistencyReport,
    ConsistencyResult,
    PrevisJob,
    PrevisJobEnvelope,
    PrevisJobStatus,
    ResearchBoard,
    ShotBrief,
    ShotBriefContent,
    ShotBriefEnvelope,
    SupportedDetail,
)
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
        after: tuple[datetime, str] | None = None,
        limit: int = 200,
    ) -> tuple[StoredResearchEvent, ...]:
        events = [event for event in self.events if event.session_id == session_id]
        if after is not None:
            events = [
                event
                for event in events
                if (event.occurred_at, event.event_id) > after
            ]
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


class FakePrevisService:
    def __init__(self) -> None:
        self.brief = ShotBrief(
            shot_brief_id="brief-1",
            research_session_id="pending",
            board_section_id="transportation",
            board_fingerprint="a" * 64,
            shot_type="establishing_shot",
            strictness="strict",
            duration_seconds=8,
            producer_model="gemini-test",
            prompt_version="brief-v1",
            created_at=datetime.now(UTC),
            content=ShotBriefContent(
                purpose="Production previsualization.",
                setting="Snowy Bitterroot mountain trail.",
                action="Horses move over steep terrain.",
                composition="Wide establishing view.",
                camera_motion="Slow lateral track.",
                ambience="Cold muted daylight.",
                supported_details=(
                    SupportedDetail(
                        detail="Horses in snow.",
                        observation_ids=("observation-1",),
                        passage_ids=("passage-1",),
                    ),
                ),
                excluded_details=("wagons",),
                positive_prompt="Wide view of horses crossing a snowy mountain trail.",
                negative_prompt="wagons, paved roads",
            ),
        )
        self.fingerprint = "b" * 64
        self.job = PrevisJob(
            job_id="job-1",
            shot_brief_id="brief-1",
            status=PrevisJobStatus.COMPLETE,
            model="veo-test",
            request_fingerprint="c" * 64,
            estimated_cost_usd=4,
            generation_count=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            output_uri="data/previs/job-1/output.mp4",
        )
        self.report = ConsistencyReport(
            job_id="job-1",
            overall_result=ConsistencyResult.UNSUPPORTED,
            findings=(
                ConsistencyFinding(
                    label=ConsistencyLabel.UNSUPPORTED,
                    visible_detail="A wagon is visible.",
                    approximate_time_range="00:04",
                    severity="critical",
                    rationale="Wagons are unsupported.",
                ),
            ),
            correction_instructions=("Remove the wagon.",),
            critic_model="gemini-test",
            prompt_version="critic-v1",
            reviewed_at=datetime.now(UTC),
        )

    async def create_brief(self, session_id: str, board: ResearchBoard, request: object):
        del board, request
        self.brief = self.brief.model_copy(update={"research_session_id": session_id})
        return ShotBriefEnvelope(
            brief=self.brief,
            brief_fingerprint=self.fingerprint,
            estimated_cost_usd=4,
            can_generate=True,
        )

    async def generate(self, brief_id: str, approval: object) -> PrevisJobEnvelope:
        del brief_id, approval
        return PrevisJobEnvelope(
            job=self.job,
            job_fingerprint="c" * 64,
            video_url="/api/previs/jobs/job-1/video",
        )

    async def get_job(self, job_id: str) -> PrevisJobEnvelope:
        del job_id
        return PrevisJobEnvelope(
            job=self.job,
            job_fingerprint="c" * 64,
            video_url="/api/previs/jobs/job-1/video",
        )

    async def review(self, job_id: str) -> PrevisJobEnvelope:
        del job_id
        return PrevisJobEnvelope(
            job=self.job,
            job_fingerprint="c" * 64,
            report=self.report,
            video_url="/api/previs/jobs/job-1/video",
        )

    async def correct(self, job_id: str, approval: object) -> PrevisJobEnvelope:
        del job_id, approval
        return PrevisJobEnvelope(job=self.job, job_fingerprint="c" * 64)

    def read_video(self, job_id: str) -> tuple[bytes, str]:
        del job_id
        return b"fake-mp4", "video/mp4"


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


def test_previs_api_exposes_approval_job_video_review_and_correction() -> None:
    app = create_app(session_repository=FakeResearchRepository())
    app.state.service_factory = FakeBoardService
    app.state.previs_service = FakePrevisService()

    with TestClient(app) as client:
        started = client.post(
            "/api/research", json={"query": DEFAULT_PROMPT, "public_domain_only": True}
        ).json()
        session_id = started["session_id"]
        for _ in range(50):
            if client.get(f"/api/research/{session_id}").json()["status"] == "complete":
                break
            time.sleep(0.01)
        brief = client.post(
            f"/api/research/{session_id}/previs/briefs",
            json={"board_section_title": "Expedition transportation"},
        )
        assert brief.status_code == 200
        assert brief.json()["brief_fingerprint"] == "b" * 64

        generated = client.post(
            "/api/previs/brief-1/generate",
            json={"approved": True, "brief_fingerprint": "b" * 64},
        )
        assert generated.status_code == 202
        assert generated.json()["disclosure"].startswith("AI-generated")
        assert client.get("/api/previs/jobs/job-1").status_code == 200
        video = client.get("/api/previs/jobs/job-1/video")
        assert video.content == b"fake-mp4"
        assert video.headers["content-type"] == "video/mp4"

        reviewed = client.post("/api/previs/jobs/job-1/review")
        assert reviewed.json()["report"]["findings"][0]["label"] == "unsupported"
        corrected = client.post(
            "/api/previs/jobs/job-1/correct",
            json={"approved": True, "job_fingerprint": "c" * 64},
        )
        assert corrected.status_code == 202
