from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from sourcecut_api.integrations.clickhouse_mcp import ClickHouseMcpClient, ClickHouseMcpSettings
from sourcecut_api.models import (
    CorrectionApproval,
    GenerationApproval,
    PrevisJobEnvelope,
    ResearchBoard,
    ShotBriefEnvelope,
    ShotBriefRequest,
    VerifiedAsset,
)
from sourcecut_api.services.board import ResearchBoardService, create_visual_inspector
from sourcecut_api.services.previs import (
    PrevisBlockedError,
    PrevisConflictError,
    PrevisNotFoundError,
    PrevisService,
    create_previs_service,
)

TERMINAL_STATUSES = {"complete", "failed"}
DEFAULT_PROMPT = (
    "Build a historically grounded visual research board for the Corps of Discovery crossing "
    "the Bitterroot Mountains in September 1805."
)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=10, max_length=2_000)
    public_domain_only: bool = True


class ResearchStarted(BaseModel):
    session_id: str
    status: str
    events_url: str


class TimelineEvent(BaseModel):
    sequence: int
    stage: str
    status: str
    message: str


@dataclass(slots=True)
class ResearchSession:
    session_id: str
    prompt: str
    status: str = "queued"
    events: list[TimelineEvent] = field(default_factory=list)
    board: ResearchBoard | None = None
    error: str = ""


def create_app() -> FastAPI:
    app = FastAPI(title="SourceCut Research API", version="0.1.0")
    origins = [
        value.strip()
        for value in os.getenv("SOURCECUT_WEB_ORIGINS", "http://localhost:3000").split(",")
        if value.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.sessions = {}
    app.state.service_factory = _board_service
    app.state.previs_service_factory = create_previs_service
    app.state.previs_service = None

    @app.exception_handler(PrevisNotFoundError)
    async def previs_not_found(
        request: Request, error: PrevisNotFoundError
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(PrevisBlockedError)
    async def previs_blocked(
        request: Request, error: PrevisBlockedError
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(PrevisConflictError)
    async def previs_conflict(
        request: Request, error: PrevisConflictError
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/research", response_model=ResearchStarted, status_code=202)
    async def start_research(request: ResearchRequest) -> ResearchStarted:
        session_id = str(uuid.uuid4())
        session = ResearchSession(session_id=session_id, prompt=request.query)
        app.state.sessions[session_id] = session
        asyncio.create_task(_run_session(app, session))
        return ResearchStarted(
            session_id=session_id,
            status=session.status,
            events_url=f"/api/research/{session_id}/events",
        )

    @app.get("/api/research/{session_id}")
    async def get_research(session_id: str) -> dict[str, Any]:
        session = _session(app, session_id)
        return {
            "session_id": session.session_id,
            "status": session.status,
            "error": session.error,
            "board": session.board.model_dump(mode="json") if session.board else None,
        }

    @app.get("/api/research/{session_id}/events")
    async def stream_research(session_id: str) -> StreamingResponse:
        session = _session(app, session_id)

        async def events() -> Any:
            cursor = 0
            while session.status not in TERMINAL_STATUSES or cursor < len(session.events):
                while cursor < len(session.events):
                    event = session.events[cursor]
                    cursor += 1
                    yield (
                        f"id: {event.sequence}\nevent: progress\n"
                        f"data: {event.model_dump_json()}\n\n"
                    )
                await asyncio.sleep(0.1)
            yield f"event: done\ndata: {json.dumps({'status': session.status})}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/api/research/{session_id}/assets/{asset_id}")
    async def get_asset(session_id: str, asset_id: str) -> dict[str, Any]:
        session = _session(app, session_id)
        asset = _find_asset(session, asset_id)
        return asset.model_dump(mode="json")

    @app.get("/api/research/{session_id}/assets/{asset_id}/thumbnail")
    async def get_thumbnail(session_id: str, asset_id: str) -> FileResponse:
        session = _session(app, session_id)
        asset = _find_asset(session, asset_id)
        path = _approved_thumbnail(asset.asset.thumbnail_path)
        return FileResponse(path)

    @app.post(
        "/api/research/{session_id}/previs/briefs",
        response_model=ShotBriefEnvelope,
    )
    async def create_previs_brief(
        session_id: str, request: ShotBriefRequest
    ) -> ShotBriefEnvelope:
        session = _session(app, session_id)
        if session.board is None or session.status != "complete":
            raise HTTPException(status_code=409, detail="Research Board is not ready")
        return await _previs(app).create_brief(session_id, session.board, request)

    @app.post(
        "/api/previs/{shot_brief_id}/generate",
        response_model=PrevisJobEnvelope,
        status_code=202,
    )
    async def generate_previs(
        shot_brief_id: str, approval: GenerationApproval
    ) -> PrevisJobEnvelope:
        return await _previs(app).generate(shot_brief_id, approval)

    @app.get("/api/previs/jobs/{job_id}", response_model=PrevisJobEnvelope)
    async def get_previs_job(job_id: str) -> PrevisJobEnvelope:
        return await _previs(app).get_job(job_id)

    @app.post(
        "/api/previs/jobs/{job_id}/review", response_model=PrevisJobEnvelope
    )
    async def review_previs(job_id: str) -> PrevisJobEnvelope:
        return await _previs(app).review(job_id)

    @app.post(
        "/api/previs/jobs/{job_id}/correct",
        response_model=PrevisJobEnvelope,
        status_code=202,
    )
    async def correct_previs(
        job_id: str, approval: CorrectionApproval
    ) -> PrevisJobEnvelope:
        return await _previs(app).correct(job_id, approval)

    @app.get("/api/previs/jobs/{job_id}/video")
    async def get_previs_video(job_id: str) -> Response:
        content, mime_type = _previs(app).read_video(job_id)
        return Response(content=content, media_type=mime_type)

    @app.get("/api/passages/{passage_id}")
    async def get_passage(passage_id: str) -> dict[str, Any]:
        return await ClickHouseMcpClient(ClickHouseMcpSettings.from_env()).get_passage(
            passage_id
        )

    return app


async def _run_session(app: FastAPI, session: ResearchSession) -> None:
    try:
        _event(session, "plan", "complete", "Research plan fixed to September 9–30, 1805.")
        session.status = "researching"
        _event(
            session,
            "evidence",
            "active",
            "ClickHouse MCP is comparing stored Lewis and Clark passages.",
        )
        service = app.state.service_factory()
        session.board = await service.build_board(session.prompt)
        _event(
            session,
            "media",
            "complete",
            "ClickHouse MCP returned rights-aware local Library of Congress assets.",
        )
        _event(
            session,
            "verification",
            "complete",
            "Gemini inspection and provenance guardrails finished.",
        )
        session.status = "complete"
        _event(session, "board", "complete", "Research board is ready for review.")
    except Exception as error:
        session.status = "failed"
        session.error = str(error)
        _event(session, "error", "failed", "Research failed. Check MCP and Gemini configuration.")


def _board_service() -> ResearchBoardService:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    inspector = create_visual_inspector(api_key=api_key) if api_key else None
    return ResearchBoardService(
        ClickHouseMcpClient(ClickHouseMcpSettings.from_env()),
        visual_inspector=inspector,
    )


def _previs(app: FastAPI) -> PrevisService:
    if app.state.previs_service is None:
        app.state.previs_service = app.state.previs_service_factory()
    return app.state.previs_service


def _event(session: ResearchSession, stage: str, status: str, message: str) -> None:
    session.events.append(
        TimelineEvent(
            sequence=len(session.events) + 1,
            stage=stage,
            status=status,
            message=message,
        )
    )


def _session(app: FastAPI, session_id: str) -> ResearchSession:
    session = app.state.sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Research session was not found")
    return session


def _find_asset(session: ResearchSession, asset_id: str) -> VerifiedAsset:
    if session.board is None:
        raise HTTPException(status_code=409, detail="Research board is not ready")
    for asset in session.board.reviewed_assets:
        if asset.asset.asset_id == asset_id:
            return asset
    raise HTTPException(status_code=404, detail="Asset was not found in this board")


def _approved_thumbnail(value: str) -> Path:
    root = Path("data/archive-cache/loc").resolve()
    path = Path(value).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="Cached thumbnail was not found")
    return path


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "sourcecut_api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )


if __name__ == "__main__":
    main()
