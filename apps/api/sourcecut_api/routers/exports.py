from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from sourcecut_api.models.export import (
    BoardExportRequest,
    ExportJob,
    SharedBoard,
    ShareLink,
    ShareRequest,
)
from sourcecut_api.services.export import (
    ExportNotFoundError,
    ExportTokenError,
    OdysseyExportService,
)
from sourcecut_api.services.odyssey_board import (
    BoardNotFoundError,
    BoardRevisionNotFoundError,
)


def create_export_router(service: OdysseyExportService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["odyssey-exports"])

    @router.post("/boards/{board_id}/exports", response_model=ExportJob, status_code=202)
    async def create_export(board_id: str, request: BoardExportRequest) -> ExportJob:
        try:
            return service.create_export(board_id, request)
        except (BoardNotFoundError, BoardRevisionNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Board revision was not found") from error

    @router.get("/exports/{job_id}/download")
    async def download_export(job_id: str, token: str = Query(min_length=10)) -> Response:
        try:
            artifact = service.download(job_id, token)
        except ExportNotFoundError as error:
            raise HTTPException(status_code=404, detail="Export was not found") from error
        except ExportTokenError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        return Response(
            content=artifact.content,
            media_type=artifact.job.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.job.filename}"',
                "X-Content-SHA256": artifact.job.artifact_sha256,
            },
        )

    @router.post("/boards/{board_id}/shares", response_model=ShareLink, status_code=201)
    async def share_board(board_id: str, request: ShareRequest) -> ShareLink:
        try:
            return service.share(board_id, request.revision_id, request.expires_in_days)
        except (BoardNotFoundError, BoardRevisionNotFoundError) as error:
            raise HTTPException(status_code=404, detail="Board revision was not found") from error

    @router.get("/shared/boards/{share_token}", response_model=SharedBoard)
    async def shared_board(share_token: str) -> SharedBoard:
        try:
            return service.shared_board(share_token)
        except ExportNotFoundError as error:
            raise HTTPException(status_code=404, detail="Shared board was not found") from error
        except ExportTokenError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

    return router
