from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from sourcecut_api.models.odyssey_board import (
    BoardCreate,
    BoardPatch,
    BoardRevision,
    OdysseyBoard,
    SectionRegeneration,
    SnapshotRequest,
)
from sourcecut_api.services.odyssey_board import (
    BoardConflictError,
    BoardNotFoundError,
    BoardRevisionNotFoundError,
    OdysseyBoardService,
)


def create_board_router(service: OdysseyBoardService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["odyssey-boards"])

    @router.post("/boards", response_model=OdysseyBoard, status_code=201)
    async def create_board(request: BoardCreate) -> OdysseyBoard:
        return service.create(request)

    @router.get("/boards/{board_id}", response_model=OdysseyBoard)
    async def get_board(board_id: str) -> OdysseyBoard:
        return _board_or_404(service, board_id)

    @router.patch("/boards/{board_id}", response_model=OdysseyBoard)
    async def patch_board(board_id: str, request: BoardPatch) -> OdysseyBoard:
        try:
            return service.patch(board_id, request)
        except BoardNotFoundError as error:
            raise HTTPException(status_code=404, detail="Board was not found") from error
        except BoardConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.post("/boards/{board_id}/duplicate", response_model=OdysseyBoard, status_code=201)
    async def duplicate_board(board_id: str) -> OdysseyBoard:
        try:
            return service.duplicate(board_id)
        except BoardNotFoundError as error:
            raise HTTPException(status_code=404, detail="Board was not found") from error

    @router.post("/boards/{board_id}/snapshot", response_model=BoardRevision, status_code=201)
    async def snapshot_board(board_id: str, request: SnapshotRequest) -> BoardRevision:
        try:
            return service.snapshot(
                board_id,
                expected_revision_id=request.expected_revision_id,
                actor=request.actor,
            )
        except BoardNotFoundError as error:
            raise HTTPException(status_code=404, detail="Board was not found") from error
        except BoardConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/boards/{board_id}/revisions", response_model=tuple[BoardRevision, ...])
    async def list_revisions(board_id: str) -> tuple[BoardRevision, ...]:
        try:
            return service.revisions(board_id)
        except BoardNotFoundError as error:
            raise HTTPException(status_code=404, detail="Board was not found") from error

    @router.post(
        "/boards/{board_id}/sections/{section_id}/regenerate",
        response_model=BoardRevision,
        status_code=201,
    )
    async def regenerate_section(
        board_id: str, section_id: str, request: SectionRegeneration
    ) -> BoardRevision:
        try:
            return service.regenerate_section(board_id, section_id, request)
        except BoardNotFoundError as error:
            raise HTTPException(status_code=404, detail="Board or section was not found") from error
        except BoardConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.post(
        "/boards/{board_id}/revisions/{revision_id}/accept",
        response_model=OdysseyBoard,
    )
    async def accept_candidate(
        board_id: str,
        revision_id: str,
        expected_revision_id: Annotated[str, Query(min_length=1)],
        actor: Annotated[str, Query(min_length=1, max_length=120)] = "public-user",
    ) -> OdysseyBoard:
        try:
            return service.accept_candidate(
                board_id,
                revision_id,
                expected_revision_id=expected_revision_id,
                actor=actor,
            )
        except BoardNotFoundError as error:
            raise HTTPException(status_code=404, detail="Board was not found") from error
        except BoardRevisionNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="Candidate revision was not found"
            ) from error
        except BoardConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return router


def _board_or_404(service: OdysseyBoardService, board_id: str) -> OdysseyBoard:
    try:
        return service.get(board_id)
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board was not found") from error
