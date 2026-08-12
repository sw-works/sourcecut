from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query

from sourcecut_api.models.curation import (
    CorpusRelease,
    CorpusReleaseCreate,
    CoverageDashboard,
    CurationAuditEvent,
    CurationDecision,
    CurationProposalCreate,
    CurationRecord,
    CurationTarget,
    DerivedRebuild,
    DerivedRebuildRequest,
    ImportRun,
    ImportRunRequest,
    ReleaseComparison,
    ReleaseManifestInput,
    ReleasePromotion,
    ReleaseRollback,
    ReviewStatus,
)
from sourcecut_api.services.curation import (
    CurationConflictError,
    CurationNotFoundError,
    CurationValidationError,
    OdysseyCurationService,
)


def create_curation_router(service: OdysseyCurationService, admin_key: str) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/odyssey", tags=["odyssey-curation"])

    def authorize(x_sourcecut_admin_key: Annotated[str, Header()] = "") -> None:
        if not admin_key:
            raise HTTPException(status_code=503, detail="Admin authentication is not configured")
        if not hmac.compare_digest(x_sourcecut_admin_key, admin_key):
            raise HTTPException(status_code=401, detail="Invalid admin credential")

    @router.post("/proposals", response_model=CurationRecord, status_code=201)
    async def create_proposal(
        request: CurationProposalCreate,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> CurationRecord:
        authorize(x_sourcecut_admin_key)
        try:
            return service.propose(request)
        except CurationValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/reviews", response_model=tuple[CurationRecord, ...])
    async def reviews(
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
        status: ReviewStatus | None = Query(default=None),
        target: CurationTarget | None = Query(default=None),
    ) -> tuple[CurationRecord, ...]:
        authorize(x_sourcecut_admin_key)
        return service.list_records(status=status, target=target)

    @router.get("/proposals/{record_id}/history", response_model=tuple[CurationRecord, ...])
    async def history(
        record_id: str, x_sourcecut_admin_key: Annotated[str, Header()] = ""
    ) -> tuple[CurationRecord, ...]:
        authorize(x_sourcecut_admin_key)
        try:
            return service.history(record_id)
        except CurationNotFoundError as error:
            raise HTTPException(status_code=404, detail="Curation record was not found") from error

    @router.post("/proposals/{record_id}/decisions", response_model=CurationRecord)
    async def decide(
        record_id: str,
        request: CurationDecision,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> CurationRecord:
        authorize(x_sourcecut_admin_key)
        try:
            return service.decide(record_id, request)
        except CurationNotFoundError as error:
            raise HTTPException(status_code=404, detail="Curation record was not found") from error
        except CurationConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except CurationValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/audit", response_model=tuple[CurationAuditEvent, ...])
    async def audit(
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> tuple[CurationAuditEvent, ...]:
        authorize(x_sourcecut_admin_key)
        return service.audit()

    @router.post("/imports", response_model=ImportRun, status_code=201)
    async def register_import(
        request: ImportRunRequest,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> ImportRun:
        authorize(x_sourcecut_admin_key)
        return service.register_import(request)

    @router.post("/releases/compare", response_model=ReleaseComparison)
    async def compare_releases(
        current: ReleaseManifestInput,
        candidate: ReleaseManifestInput,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> ReleaseComparison:
        authorize(x_sourcecut_admin_key)
        return service.compare(current, candidate)

    @router.post("/releases", response_model=CorpusRelease, status_code=201)
    async def create_release(
        request: CorpusReleaseCreate,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> CorpusRelease:
        authorize(x_sourcecut_admin_key)
        try:
            return service.create_release(request)
        except (CurationNotFoundError, CurationValidationError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/releases/{release_id}/promote", response_model=CorpusRelease)
    async def promote_release(
        release_id: str,
        request: ReleasePromotion,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> CorpusRelease:
        authorize(x_sourcecut_admin_key)
        try:
            return service.promote_release(release_id, actor_id=request.actor_id, note=request.note)
        except CurationNotFoundError as error:
            raise HTTPException(status_code=404, detail="Release was not found") from error
        except CurationValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/releases/rollback", response_model=CorpusRelease)
    async def rollback_release(
        request: ReleaseRollback,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> CorpusRelease:
        authorize(x_sourcecut_admin_key)
        try:
            return service.rollback(
                request.release_id, actor_id=request.actor_id, reason=request.reason
            )
        except CurationValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/rebuilds", response_model=DerivedRebuild, status_code=202)
    async def rebuild(
        request: DerivedRebuildRequest,
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> DerivedRebuild:
        authorize(x_sourcecut_admin_key)
        return service.rebuild(request)

    @router.get("/coverage", response_model=CoverageDashboard)
    async def coverage(
        x_sourcecut_admin_key: Annotated[str, Header()] = "",
    ) -> CoverageDashboard:
        authorize(x_sourcecut_admin_key)
        return service.coverage()

    return router
