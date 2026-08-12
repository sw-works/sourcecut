from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from sourcecut_api.models.narrative import SpeechView, TimelineEventView, TimelineResponse
from sourcecut_api.services.narrative import build_speeches, build_timeline_response


def create_narrative_router(mcp_client_factory: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["odyssey-narrative"])

    @router.get("/timelines/odyssey", response_model=TimelineResponse)
    async def timeline(
        mode: str = Query("reading", pattern="^(reading|story)$"),
        characters: list[str] = Query(default=[]),
        places: list[str] = Query(default=[]),
        themes: list[str] = Query(default=[]),
        narrative_levels: list[str] = Query(default=[]),
        books: list[int] = Query(default=[]),
    ) -> TimelineResponse:
        try:
            rows = await mcp_client_factory().get_odyssey_timeline(
                mode=mode,
                character_ids=characters,
                place_ids=places,
                theme_ids=themes,
                narrative_levels=narrative_levels,
                books=books,
            )
            return build_timeline_response(mode, rows)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/events/{event_id}", response_model=TimelineEventView)
    async def event(event_id: str) -> TimelineEventView:
        try:
            rows = await mcp_client_factory().get_odyssey_event(event_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        response = build_timeline_response("reading", rows)
        if not response.events:
            raise HTTPException(status_code=404, detail="Narrative event was not found")
        return response.events[0]

    @router.get("/speeches", response_model=tuple[SpeechView, ...])
    async def speeches(
        speakers: list[str] = Query(default=[]), books: list[int] = Query(default=[])
    ) -> tuple[SpeechView, ...]:
        try:
            return build_speeches(await mcp_client_factory().get_odyssey_speeches(speakers, books))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return router
