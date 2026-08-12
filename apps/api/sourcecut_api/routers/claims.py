from __future__ import annotations

from fastapi import APIRouter, HTTPException

from sourcecut_api.models.claim import (
    ClaimCreate,
    ClaimMatrixRow,
    ClaimRecord,
    ClaimTrace,
    PublicationDecision,
)
from sourcecut_api.services.claim_validation import (
    ClaimNotFoundError,
    ClaimValidationService,
)


def create_claim_router(service: ClaimValidationService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["odyssey-claims"])

    @router.post("/claims", response_model=ClaimRecord, status_code=201)
    async def create_claim(candidate: ClaimCreate) -> ClaimRecord:
        return await service.create(candidate)

    @router.get("/claims", response_model=tuple[ClaimRecord, ...])
    async def list_claims() -> tuple[ClaimRecord, ...]:
        return service.list()

    @router.get("/claims/matrix", response_model=tuple[ClaimMatrixRow, ...])
    async def claim_matrix() -> tuple[ClaimMatrixRow, ...]:
        return service.matrix()

    @router.get("/claims/{claim_id}", response_model=ClaimRecord)
    async def get_claim(claim_id: str) -> ClaimRecord:
        try:
            return service.get(claim_id)
        except ClaimNotFoundError as error:
            raise HTTPException(status_code=404, detail="Claim was not found") from error

    @router.get("/claims/{claim_id}/trace", response_model=ClaimTrace)
    async def trace_claim(claim_id: str) -> ClaimTrace:
        try:
            return await service.trace(claim_id)
        except ClaimNotFoundError as error:
            raise HTTPException(status_code=404, detail="Claim was not found") from error

    @router.post(
        "/claims/{claim_id}/publication",
        response_model=PublicationDecision,
    )
    async def check_publication(claim_id: str) -> PublicationDecision:
        try:
            decision = service.publication_decision(claim_id)
        except ClaimNotFoundError as error:
            raise HTTPException(status_code=404, detail="Claim was not found") from error
        if not decision.allowed:
            raise HTTPException(
                status_code=409,
                detail={"message": "Claim is not publication-ready", "reasons": decision.reasons},
            )
        return decision

    return router
