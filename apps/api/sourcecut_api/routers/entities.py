from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException


def create_entity_router(mcp_client_factory: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["odyssey-entities-themes"])

    @router.get("/entities")
    async def entities() -> list[dict[str, object]]:
        return await mcp_client_factory().list_odyssey_entities()

    @router.get("/entities/{entity_id}")
    async def entity(entity_id: str) -> dict[str, object]:
        try:
            rows = await mcp_client_factory().get_odyssey_entity(entity_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not rows:
            raise HTTPException(status_code=404, detail="Classical entity was not found")
        first = rows[0]
        return {
            "entity": {
                key: first[key]
                for key in (
                    "entity_id",
                    "entity_type",
                    "canonical_name",
                    "greek_name",
                    "aliases",
                    "description",
                    "authority_uris",
                    "curation_citations",
                )
            },
            "occurrences": [row for row in rows if row.get("mention_id")],
            "annotation_notice": (
                "Mentions are exact deterministic alias matches; profiles are curated "
                "navigation aids."
            ),
        }

    @router.get("/entities/{entity_id}/occurrences")
    async def occurrences(entity_id: str) -> list[dict[str, object]]:
        return await mcp_client_factory().get_odyssey_entity(entity_id)

    @router.get("/relationships")
    async def relationships(entity_id: str = "") -> list[dict[str, object]]:
        return await mcp_client_factory().get_odyssey_relationships(entity_id)

    @router.get("/themes")
    async def themes() -> list[dict[str, object]]:
        return await mcp_client_factory().list_odyssey_themes()

    @router.get("/themes/{theme_id}")
    async def theme(theme_id: str) -> dict[str, object]:
        try:
            rows = await mcp_client_factory().get_odyssey_theme(theme_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not rows:
            raise HTTPException(status_code=404, detail="Theme was not found")
        return {
            "theme": {
                key: rows[0][key]
                for key in (
                    "theme_id",
                    "title",
                    "description",
                    "aliases",
                    "bibliography",
                    "curator",
                )
            },
            "passages": [row for row in rows if row.get("theme_passage_id")],
            "editorial_notice": (
                "Theme links are curated interpretation, not primary textual facts."
            ),
        }

    return router
