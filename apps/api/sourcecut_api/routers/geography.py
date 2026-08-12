from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query


def create_geography_router(mcp_client_factory: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["odyssey-geography"])

    @router.get("/maps/odyssey/config")
    async def config() -> dict[str, object]:
        return {
            "default_mode": "textual_sequence",
            "max_hypotheses": 3,
            "coordinate_policy": (
                "Coordinates describe authority places or named proposals, "
                "never textual certainty."
            ),
            "basemap": {
                "kind": "bounded_static_physical_context",
                "attribution": "Natural Earth; Pleiades contributors CC BY 3.0",
            },
        }

    @router.get("/maps/odyssey/graph")
    async def graph() -> dict[str, object]:
        return await mcp_client_factory().get_odyssey_route_graph()

    @router.get("/maps/odyssey/geojson")
    async def geojson(
        hypotheses: list[str] = Query(default=[]), classes: list[str] = Query(default=[])
    ) -> dict[str, object]:
        try:
            rows = await mcp_client_factory().get_odyssey_map_features(hypotheses, classes)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        features = []
        for row in rows:
            geometry = None
            if row.get("longitude") is not None and row.get("latitude") is not None:
                geometry = {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]}
            features.append(
                {
                    "type": "Feature",
                    "id": row["identification_id"],
                    "geometry": geometry,
                    "properties": {
                        **row,
                        "feature_kind": "place_identification",
                        "source_ids": row.get("scholarly_source_ids", []),
                        "event_ids": [],
                        "citation_ids": [],
                        "display_style": f"{row['identification_class']}:{row['confidence']}",
                    },
                }
            )
        return {
            "type": "FeatureCollection",
            "features": features,
            "notice": "Null geometry is intentional; use the voyage graph for unlocated places.",
            "export_metadata": {
                "active_hypotheses": hypotheses,
                "active_classes": classes,
                "legend": {
                    "identified": "solid marker",
                    "traditional": "outlined marker",
                    "hypothesized": "patterned hypothesis-colored marker",
                    "mythic_unlocated": "graph or Beyond register only",
                },
                "attribution": [
                    "Pleiades contributors, CC BY 3.0",
                    "Physical context: Natural Earth, public domain",
                ],
            },
        }

    @router.get("/places/{poetic_place_id}")
    async def place(poetic_place_id: str) -> dict[str, object]:
        try:
            rows = await mcp_client_factory().get_odyssey_poetic_place(poetic_place_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not rows:
            raise HTTPException(status_code=404, detail="Poetic place was not found")
        return {"poetic_place_id": poetic_place_id, "identifications": rows}

    @router.get("/route-hypotheses")
    async def hypotheses() -> list[dict[str, object]]:
        return await mcp_client_factory().get_odyssey_route_hypotheses()

    @router.get("/route-hypotheses/{hypothesis_id}")
    async def hypothesis(hypothesis_id: str) -> dict[str, object]:
        rows = await mcp_client_factory().get_odyssey_route_hypotheses(hypothesis_id)
        if not rows:
            raise HTTPException(status_code=404, detail="Route hypothesis was not found")
        return rows[0]

    return router
