from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from pipelines.embeddings import EmbeddingSettings, create_embedder
from sourcecut_api.constants import BITTERROOT_END, BITTERROOT_START
from sourcecut_api.corpora import CorpusRegistry, create_corpus_registry
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.integrations.clickhouse_mcp import (
    ClickHouseMcpClient,
    ClickHouseMcpSettings,
    query_rows,
)
from sourcecut_api.middleware import RequestSafetyMiddleware
from sourcecut_api.models import (
    CorrectionApproval,
    GenerationApproval,
    PrevisJobEnvelope,
    ResearchBoard,
    ShotBriefEnvelope,
    ShotBriefRequest,
    VerifiedAsset,
)
from sourcecut_api.repositories import (
    LazyClickHouseBoardRepository,
    LazyClickHouseCurationStore,
    ResearchEventRepository,
    StoredResearchEvent,
)
from sourcecut_api.routers import (
    create_board_router,
    create_claim_router,
    create_classical_text_router,
    create_corpus_router,
    create_curation_router,
    create_entity_router,
    create_export_router,
    create_geography_router,
    create_linguistic_router,
    create_narrative_router,
    create_visual_culture_router,
)
from sourcecut_api.services.board import ResearchBoardService, create_visual_inspector
from sourcecut_api.services.claim_validation import ClaimValidationService
from sourcecut_api.services.curation import OdysseyCurationService
from sourcecut_api.services.export import OdysseyExportService
from sourcecut_api.services.linguistic import MemorySavedSearchStore
from sourcecut_api.services.odyssey_board import OdysseyBoardService
from sourcecut_api.services.previs import (
    PrevisBlockedError,
    PrevisConflictError,
    PrevisNotFoundError,
    PrevisService,
    create_previs_service,
)
from sourcecut_api.services.readiness import readiness_report

TERMINAL_STATUSES = {"complete", "failed"}
ENTITIES_CACHE_TTL_SECONDS = 300.0
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
    event_id: str
    event_type: str
    stage: str
    status: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0


@dataclass(slots=True)
class ResearchSession:
    session_id: str
    prompt: str
    status: str = "queued"
    board: ResearchBoard | None = None
    error: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def create_app(
    *,
    session_repository: Any | None = None,
    corpus_registry: CorpusRegistry | None = None,
    saved_search_store: MemorySavedSearchStore | None = None,
    claim_service: ClaimValidationService | None = None,
    board_store: Any | None = None,
    curation_store: Any | None = None,
    admin_key: str | None = None,
) -> FastAPI:
    app = FastAPI(title="SourceCut Research API", version="0.1.0")
    origins = [
        value.strip()
        for value in os.getenv("SOURCECUT_WEB_ORIGINS", "http://localhost:3000").split(",")
        if value.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID", "X-SourceCut-Admin-Key"],
    )
    app.add_middleware(RequestSafetyMiddleware)
    app.state.sessions = {}
    app.state.session_repository = session_repository
    app.state.service_factory = _board_service
    app.state.previs_service_factory = create_previs_service
    app.state.previs_service = None
    app.state.mcp_client_factory = lambda: ClickHouseMcpClient(
        ClickHouseMcpSettings.from_env()
    )
    app.state.entities_cache = None
    app.state.corpus_registry = corpus_registry or create_corpus_registry()
    app.state.saved_search_store = saved_search_store or MemorySavedSearchStore()
    app.state.claim_service = claim_service or ClaimValidationService(
        lambda: app.state.mcp_client_factory()
    )
    resolved_board_store = board_store or LazyClickHouseBoardRepository(get_clickhouse_client)
    app.state.odyssey_board_service = OdysseyBoardService(resolved_board_store)
    app.state.odyssey_export_service = OdysseyExportService(app.state.odyssey_board_service)
    app.state.odyssey_curation_service = OdysseyCurationService(
        curation_store or LazyClickHouseCurationStore(get_clickhouse_client)
    )
    app.include_router(create_corpus_router(app.state.corpus_registry))
    app.include_router(
        create_classical_text_router(
            app.state.corpus_registry, lambda: app.state.mcp_client_factory()
        )
    )
    app.include_router(
        create_linguistic_router(
            lambda: app.state.mcp_client_factory(), app.state.saved_search_store
        )
    )
    app.include_router(create_claim_router(app.state.claim_service))
    app.include_router(create_board_router(app.state.odyssey_board_service))
    app.include_router(create_export_router(app.state.odyssey_export_service))
    app.include_router(
        create_curation_router(
            app.state.odyssey_curation_service,
            admin_key if admin_key is not None else os.getenv("SOURCECUT_ADMIN_KEY", ""),
        )
    )
    app.include_router(create_narrative_router(lambda: app.state.mcp_client_factory()))
    app.include_router(create_geography_router(lambda: app.state.mcp_client_factory()))
    app.include_router(create_entity_router(lambda: app.state.mcp_client_factory()))
    app.include_router(create_visual_culture_router(lambda: app.state.mcp_client_factory()))

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

    @app.get("/readyz")
    async def ready() -> dict[str, Any]:
        return readiness_report()

    @app.post("/api/research", response_model=ResearchStarted, status_code=202)
    async def start_research(request: ResearchRequest) -> ResearchStarted:
        session_id = str(uuid.uuid4())
        session = ResearchSession(session_id=session_id, prompt=request.query)
        await asyncio.to_thread(_save_session, app, session)
        _record_event(
            app,
            session_id,
            "session_created",
            "session",
            "complete",
            "Research session created.",
        )
        app.state.sessions[session_id] = session
        asyncio.create_task(_run_session(app, session))
        return ResearchStarted(
            session_id=session_id,
            status=session.status,
            events_url=f"/api/research/{session_id}/events",
        )

    @app.get("/api/research/{session_id}")
    async def get_research(session_id: str) -> dict[str, Any]:
        session = await asyncio.to_thread(_session, app, session_id)
        return {
            "session_id": session.session_id,
            "status": session.status,
            "error": session.error,
            "board": session.board.model_dump(mode="json") if session.board else None,
        }

    @app.get("/api/research/{session_id}/events")
    async def stream_research(session_id: str) -> StreamingResponse:
        await asyncio.to_thread(_session, app, session_id)

        async def events() -> Any:
            cursor: datetime | None = None
            seen: set[str] = set()
            sequence = 0
            terminal_empty_polls = 0
            while terminal_empty_polls < 2:
                stored_events = await asyncio.to_thread(
                    _research_store(app).list_events, session_id, after=cursor
                )
                fresh = [event for event in stored_events if event.event_id not in seen]
                for stored in fresh:
                    sequence += 1
                    event = _timeline_event(sequence, stored)
                    seen.add(stored.event_id)
                    cursor = stored.occurred_at
                    yield (
                        f"id: {event.event_id}\nevent: progress\n"
                        f"data: {event.model_dump_json()}\n\n"
                    )
                current = await asyncio.to_thread(_session, app, session_id)
                if current.status in TERMINAL_STATUSES and not fresh:
                    terminal_empty_polls += 1
                else:
                    terminal_empty_polls = 0
                await asyncio.sleep(0.25)
            current = await asyncio.to_thread(_session, app, session_id)
            yield f"event: done\ndata: {json.dumps({'status': current.status})}\n\n"

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

    @app.get("/api/assets/{asset_id}")
    async def get_stored_asset(asset_id: str) -> dict[str, Any]:
        asset = await _stored_asset(app, asset_id)
        if asset.get("thumbnail_path"):
            asset["thumbnail_url"] = f"/api/assets/{asset_id}/thumbnail"
        return asset

    @app.get("/api/assets/{asset_id}/thumbnail")
    async def get_stored_asset_thumbnail(asset_id: str) -> FileResponse:
        asset = await _stored_asset(app, asset_id)
        return FileResponse(_approved_thumbnail(str(asset.get("thumbnail_path", ""))))

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
        return await app.state.mcp_client_factory().get_passage(passage_id)

    @app.get("/api/entities")
    async def get_entities() -> list[dict[str, Any]]:
        cached = app.state.entities_cache
        if cached is not None and time.monotonic() - cached[0] < ENTITIES_CACHE_TTL_SECONDS:
            return cached[1]
        entities = await _mcp_query_dicts(
            app,
            "SELECT entity_id, entity_type, canonical_name, alt_names "
            "FROM sourcecut.entities FINAL ORDER BY canonical_name LIMIT 200",
        )
        app.state.entities_cache = (time.monotonic(), entities)
        return entities

    @app.get("/api/entities/{entity_id}/mentions")
    async def get_entity_mentions(
        entity_id: str, start: int = BITTERROOT_START, end: int = BITTERROOT_END
    ) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[a-z0-9-]+", entity_id) or not (18000101 <= start <= end <= 18991231):
            raise HTTPException(status_code=422, detail="Invalid entity or date window")
        return await _mcp_query_dicts(
            app,
            "SELECT mention_id, entity_id, passage_id, entry_date, author_id, "
            "author_display_name, source_quote, source_start, source_end, extractor "
            "FROM sourcecut.entity_mentions_window("
            f"entity='{entity_id}', start={start}, end={end}) "
            "LIMIT 500",
        )

    return app


async def _mcp_query_dicts(app: FastAPI, query: str) -> list[dict[str, Any]]:
    payload = await app.state.mcp_client_factory().call_tool("run_query", {"query": query})
    columns, rows = query_rows(payload)
    return [dict(zip(columns, row, strict=True)) for row in rows]


async def _run_session(app: FastAPI, session: ResearchSession) -> None:
    try:
        session.status = "researching"
        await asyncio.to_thread(_save_session, app, session)
        _record_event(
            app,
            session.session_id,
            "stage_started",
            "evidence",
            "active",
            "Evidence and media research started.",
        )
        service = app.state.service_factory()
        if hasattr(service, "event_sink"):
            service.event_sink = lambda *event: _record_event(
                app, session.session_id, *event
            )
        session.board = await service.build_board(session.prompt)
        session.status = "complete"
        # Terminal events are durable (wait_for_async_insert=1) and land before
        # the terminal status write, so the SSE stream cannot close while they
        # sit in the async-insert buffer.
        await asyncio.to_thread(
            _record_event,
            app,
            session.session_id,
            "stage_completed",
            "research",
            "complete",
            "Evidence, media, and verification research completed.",
            None,
            0,
            True,
        )
        await asyncio.to_thread(
            _record_event,
            app,
            session.session_id,
            "board_completed",
            "board",
            "complete",
            "Research board is ready for review.",
            {"requirement_count": len(session.board.evidence_matrix)},
            0,
            True,
        )
        await asyncio.to_thread(_save_session, app, session)
    except Exception as error:
        session.status = "failed"
        session.error = str(error)
        await asyncio.to_thread(
            _record_event,
            app,
            session.session_id,
            "session_failed",
            "error",
            "failed",
            "Research failed. Check MCP and Gemini configuration.",
            {"error_type": type(error).__name__},
            0,
            True,
        )
        await asyncio.to_thread(_save_session, app, session)


def _board_service() -> ResearchBoardService:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    inspector = create_visual_inspector(api_key=api_key) if api_key else None
    embedding_settings = EmbeddingSettings.from_env()
    embedder = create_embedder(embedding_settings) if embedding_settings.enabled else None
    return ResearchBoardService(
        ClickHouseMcpClient(ClickHouseMcpSettings.from_env()),
        visual_inspector=inspector,
        embedder=embedder,
    )


def _previs(app: FastAPI) -> PrevisService:
    if app.state.previs_service is None:
        app.state.previs_service = app.state.previs_service_factory()
    return app.state.previs_service


def _research_store(app: FastAPI) -> ResearchEventRepository:
    if app.state.session_repository is None:
        app.state.session_repository = ResearchEventRepository(get_clickhouse_client())
    return app.state.session_repository


def _save_session(app: FastAPI, session: ResearchSession) -> None:
    _research_store(app).save_session(
        session_id=session.session_id,
        status=session.status,
        prompt=session.prompt,
        board_json=session.board.model_dump_json() if session.board else "",
        error=session.error,
        created_at=session.created_at,
    )


def _record_event(
    app: FastAPI,
    session_id: str,
    event_type: str,
    stage: str,
    status: str,
    message: str,
    payload: dict[str, Any] | None = None,
    duration_ms: int = 0,
    durable: bool = False,
) -> None:
    def write() -> None:
        _research_store(app).record(
            session_id=session_id,
            event_type=event_type,
            stage=stage,
            status=status,
            message=message,
            payload=payload,
            duration_ms=duration_ms,
            durable=durable,
        )

    # The event sink fires from async code paths; keep the blocking insert off
    # the event loop. Outside a running loop (CLI, tests), write inline.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        write()
    else:
        loop.run_in_executor(None, write)


def _session(app: FastAPI, session_id: str, *, refresh: bool = True) -> ResearchSession:
    # Read-through by default: with multiple API instances the process dict can
    # go stale, so only explicit refresh=False callers may trust the cache.
    session = None if refresh else app.state.sessions.get(session_id)
    if session is None:
        stored = _research_store(app).get_session(session_id)
        if stored is not None:
            session = ResearchSession(
                session_id=stored.session_id,
                prompt=stored.prompt,
                status=stored.status,
                board=(
                    ResearchBoard.model_validate_json(stored.board_json)
                    if stored.board_json
                    else None
                ),
                error=stored.error,
                created_at=stored.created_at,
            )
            app.state.sessions[session_id] = session
    if session is None:
        raise HTTPException(status_code=404, detail="Research session was not found")
    return session


def _timeline_event(sequence: int, event: StoredResearchEvent) -> TimelineEvent:
    return TimelineEvent(
        sequence=sequence,
        event_id=event.event_id,
        event_type=event.event_type,
        stage=event.stage,
        status=event.status,
        message=event.message,
        payload=event.payload,
        duration_ms=event.duration_ms,
    )


def _find_asset(session: ResearchSession, asset_id: str) -> VerifiedAsset:
    if session.board is None:
        raise HTTPException(status_code=409, detail="Research board is not ready")
    for asset in session.board.reviewed_assets:
        if asset.asset.asset_id == asset_id:
            return asset
    raise HTTPException(status_code=404, detail="Asset was not found in this board")


async def _stored_asset(app: FastAPI, asset_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9:_.-]{1,256}", asset_id):
        raise HTTPException(status_code=422, detail="Invalid asset ID")
    result = await app.state.mcp_client_factory().get_asset(asset_id)
    if result.get("status") != "found":
        raise HTTPException(status_code=404, detail="Asset was not found")
    asset = result.get("asset")
    if not isinstance(asset, dict):
        raise RuntimeError("ClickHouse MCP returned invalid asset metadata")
    return dict(asset)


def _approved_thumbnail(value: str) -> Path:
    root = Path("data/archive-cache").resolve()
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
