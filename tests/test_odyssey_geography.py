from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import FakeClickHouseClient
from fastapi.testclient import TestClient

from pipelines.classics import load_geography_release
from sourcecut_api.main import create_app
from sourcecut_api.repositories import ClickHouseGeographyRepository

ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "data" / "reference" / "odyssey_geography.json"


def test_geography_keeps_textual_graph_complete_and_mythic_places_unlocated() -> None:
    release = load_geography_release(RELEASE)
    assert len(release.nodes) == 15
    assert len(release.edges) == 14
    mythic = {
        p.poetic_place_id for p in release.poetic_places if p.place_class == "mythic_unlocated"
    }
    assert mythic
    assert not any(
        i.hypothesis_id == "secure_places" and i.poetic_place_id in mythic
        for i in release.identifications
    )
    assert {h.hypothesis_id for h in release.hypotheses} >= {
        "textual_sequence",
        "berard",
        "bradford",
    }


def test_geography_repository_is_idempotent() -> None:
    release = load_geography_release(RELEASE)
    client = FakeClickHouseClient("corpus")
    repository = ClickHouseGeographyRepository(client)  # type: ignore[arg-type]
    first = repository.load(release)
    second = repository.load(release)
    assert first.nodes_inserted == 15 and first.edges_inserted == 14
    assert second.nodes_inserted == second.edges_inserted == 0


class FakeMapMcp:
    async def get_odyssey_route_graph(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "route_node_id": "n1",
                    "canonical_name": "Ogygia",
                    "citation_ids": ["urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:5.1-227"],
                }
            ],
            "edges": [],
        }

    async def get_odyssey_map_features(
        self, hypotheses: list[str], classes: list[str]
    ) -> list[dict[str, Any]]:
        del hypotheses, classes
        return [
            {
                "identification_id": "id:ogygia-bradford",
                "poetic_place_id": "ogygia",
                "canonical_name": "Ogygia",
                "place_class": "mythic_unlocated",
                "hypothesis_id": "bradford",
                "identification_class": "hypothesized",
                "longitude": 14.4,
                "latitude": 35.9,
                "confidence": "disputed",
                "status": "proposal",
                "rationale": "Named proposal",
                "scholarly_source_ids": ["bradford-1963"],
            }
        ]

    async def get_odyssey_route_hypotheses(self, hypothesis_id: str = "") -> list[dict[str, Any]]:
        rows = [
            {
                "hypothesis_id": "bradford",
                "title": "Bradford route",
                "author_or_tradition": "Ernle Bradford",
                "description": "Proposal",
                "scholarly_source_ids": ["bradford-1963"],
                "license_id": "METADATA_ONLY",
                "display_order": 2,
                "is_default": False,
            }
        ]
        return [r for r in rows if not hypothesis_id or r["hypothesis_id"] == hypothesis_id]

    async def get_odyssey_poetic_place(self, poetic_place_id: str) -> list[dict[str, Any]]:
        rows = await self.get_odyssey_map_features([], [])
        return [r for r in rows if r["poetic_place_id"] == poetic_place_id]


def test_map_api_preserves_proposal_class_and_source() -> None:
    app = create_app()
    app.state.mcp_client_factory = FakeMapMcp
    client = TestClient(app)
    graph = client.get("/api/v1/maps/odyssey/graph")
    geo = client.get("/api/v1/maps/odyssey/geojson?hypotheses=bradford")
    place = client.get("/api/v1/places/ogygia")
    hypothesis = client.get("/api/v1/route-hypotheses/bradford")
    assert (
        graph.status_code == geo.status_code == place.status_code == hypothesis.status_code == 200
    )
    feature = geo.json()["features"][0]
    assert feature["properties"]["confidence"] == "disputed"
    assert feature["properties"]["source_ids"] == ["bradford-1963"]
