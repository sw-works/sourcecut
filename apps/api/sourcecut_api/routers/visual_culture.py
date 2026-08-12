from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class AssetSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(max_length=200, default="")
    relationships: tuple[str, ...] = ()
    providers: tuple[str, ...] = ()
    rights: tuple[str, ...] = ()
    cultures: tuple[str, ...] = ()
    media: tuple[str, ...] = ()
    target_kind: str = ""
    target_id: str = ""
    image_available: bool | None = None
    public_only: bool = True


def create_visual_culture_router(mcp_client_factory: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["odyssey-visual-culture"])

    @router.post("/search/assets")
    async def search(request: AssetSearchRequest) -> list[dict[str, object]]:
        return await mcp_client_factory().search_odyssey_assets(
            request.query,
            list(request.relationships),
            request.public_only,
            request.model_dump(),
        )

    @router.get("/assets/{asset_id}")
    async def asset(asset_id: str) -> dict[str, object]:
        try:
            rows = await mcp_client_factory().get_odyssey_visual_asset(asset_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not rows:
            raise HTTPException(status_code=404, detail="Visual asset was not found")
        return rows[0]

    @router.get("/assets/{asset_id}/relationships")
    async def relationships(asset_id: str) -> dict[str, object]:
        row = await asset(asset_id)
        return {
            "asset_id": asset_id,
            "relationship_class": row["relationship_class"],
            "production_use": row["production_use"],
            "limitations": row["limitations"],
            "evidence_ids": row["evidence_ids"],
            "verification_status": row["verification_status"],
        }

    return router
