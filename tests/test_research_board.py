from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from sourcecut_api.models import (
    AssetRequirement,
    BoardConfidence,
    EvidenceCitation,
    HistoricalRelationship,
    MediaAsset,
    RightsStatus,
    VisualInspection,
)
from sourcecut_api.services.board import (
    EVIDENCE_QUERY,
    MEDIA_QUERY,
    PASSAGE_EVIDENCE_QUERY,
    GeminiVisualInspector,
    ResearchBoardService,
    _semantic_passage_query,
    verify_asset,
)


def evidence_row(**changes: Any) -> dict[str, Any]:
    row = {
        "observation_id": "observation:snow",
        "passage_id": "gutenberg:lewis:1805-09-16:passage:0",
        "author_display_name": "Meriwether Lewis",
        "entry_date": 18050916,
        "category": "terrain",
        "canonical_term": "steep mountain",
        "source_quote": "the road was excessively dangerous",
        "confidence": 0.97,
    }
    row.update(changes)
    return row


def media_row(**changes: Any) -> dict[str, Any]:
    row = {
        "asset_id": "loc:map",
        "provider": "Library of Congress",
        "provider_id": "map",
        "title": "A map of Lewis and Clark's track across the Rocky Mountains",
        "description": "A map of the expedition route.",
        "creators": ["Clark, William"],
        "asset_type": "map",
        "creation_date_text": "1814",
        "creation_year": 1814,
        "subjects": ["Lewis and Clark expedition", "Rocky Mountains"],
        "places": ["Montana"],
        "source_url": "https://www.loc.gov/item/map/",
        "media_url": "https://tile.loc.gov/map.jpg",
        "thumbnail_path": "data/archive-cache/loc/thumbnails/map.jpg",
        "rights_status": "public_domain",
        "rights_text": "Public domain.",
        "historical_relationship": "NEAR_CONTEMPORARY",
        "raw_metadata": "{}",
        "metadata_sha256": "a" * 64,
    }
    row.update(changes)
    return row


class FakeMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        query = arguments["query"]
        if "sourcecut.author_date_matrix" in query:
            rows = [
                {
                    "author_id": "lewis",
                    "author_display_name": "Meriwether Lewis",
                    "entry_date": 18050916,
                    "mention_count": 1,
                    "observation_count": 1,
                    "passage_ids": ["passage:lewis"],
                },
                {
                    "author_id": "clark",
                    "author_display_name": "William Clark",
                    "entry_date": 18050916,
                    "mention_count": 0,
                    "observation_count": 0,
                    "passage_ids": [],
                },
                {
                    "author_id": "gass",
                    "author_display_name": "Patrick Gass",
                    "entry_date": 18050916,
                    "mention_count": 1,
                    "observation_count": 1,
                    "passage_ids": ["passage:gass"],
                },
            ]
        elif "sourcecut.route_waypoints" in query:
            rows = [
                {
                    "waypoint_id": "lolo-pass",
                    "entry_date": 18050916,
                    "name": "Lolo Pass",
                    "lat": 46.635,
                    "lon": -114.58,
                    "citation_passage_ids": ["passage:clark"],
                    "source_note": "NPS route map.",
                }
            ]
        elif "sourcecut.evidence_window" in query:
            rows = [
                evidence_row(),
                evidence_row(
                    observation_id="observation:clark",
                    passage_id="gutenberg:clark:1805-09-16:passage:0",
                    author_display_name="William Clark",
                ),
            ]
        else:
            rows = [
                media_row(),
                media_row(
                    asset_id="loc:photo",
                    provider_id="photo",
                    title="Bitterroot Valley mountain landscape",
                    description="A later landscape photograph.",
                    asset_type="photo, print, drawing",
                    creation_year=1942,
                    historical_relationship="LATER_REPRESENTATION",
                    metadata_sha256="b" * 64,
                ),
                media_row(
                    asset_id="loc:unrelated",
                    provider_id="unrelated",
                    title="Unrelated coastal portrait",
                    description="No route relationship.",
                    subjects=["portrait"],
                    places=["Maine"],
                    historical_relationship="LATER_REPRESENTATION",
                    metadata_sha256="c" * 64,
                ),
                media_row(
                    asset_id="loc:restricted",
                    provider_id="restricted",
                    rights_status="restricted",
                    metadata_sha256="d" * 64,
                ),
            ]
        return {"columns": list(rows[0]), "rows": rows}


class RelevantInspector:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def inspect(
        self, asset: MediaAsset, requirement: AssetRequirement
    ) -> VisualInspection:
        self.calls.append(asset.asset_id)
        return VisualInspection(
            relevant=True,
            visible_findings="A mountainous landscape is visible.",
        )


class FailingInspector:
    async def inspect(
        self, asset: MediaAsset, requirement: AssetRequirement
    ) -> VisualInspection:
        raise RuntimeError("visual service unavailable")


def test_board_uses_mcp_and_keeps_evidence_drill_down() -> None:
    mcp = FakeMcpClient()
    inspector = RelevantInspector()

    board = asyncio.run(
        ResearchBoardService(
            mcp,
            visual_inspector=inspector,
            visual_inspection_limit=1,
        ).build_board("Build a Bitterroot board for September 1805")
    )

    assert [call[0] for call in mcp.calls] == ["run_query"] * 4
    assert mcp.calls[0][1]["query"] == EVIDENCE_QUERY
    assert "sourcecut.evidence_window" in EVIDENCE_QUERY
    assert "sourcecut.observations" not in EVIDENCE_QUERY
    assert mcp.calls[2][1]["query"] == MEDIA_QUERY
    assert "sourcecut.media_assets" in mcp.calls[2][1]["query"]
    assert "sourcecut.media_assets FINAL" in MEDIA_QUERY
    assert board.evidence_matrix[0].evidence[0].source_quote == (
        "the road was excessively dangerous"
    )
    confidences = {item.confidence for item in board.reviewed_assets}
    assert BoardConfidence.HIGH in confidences
    assert BoardConfidence.INTERPRETIVE in confidences
    assert BoardConfidence.UNSUPPORTED in confidences
    assert BoardConfidence.RIGHTS_REJECTED in confidences
    assert inspector.calls == ["loc:photo"]
    assert any("interpretive" in warning for warning in board.warnings)
    assert all(section.assets for section in board.sections)
    requirement = board.evidence_matrix[0]
    assert {cell.state for cell in requirement.agreement} == {
        "mentions",
        "entry_without_mention",
        "no_entry",
    }
    assert requirement.corroboration_authors == 2
    assert requirement.corroboration_days == 1
    assert board.route_waypoints[0].waypoint_id == "lolo-pass"


def test_semantic_board_queries_clickhouse_mcp_for_passages_and_media() -> None:
    class FakeEmbedder:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def embed_query(self, text: str) -> tuple[float, ...]:
            self.calls.append(text)
            return (0.25, 0.75)

    class SemanticMcp(FakeMcpClient):
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            query = arguments["query"]
            if "cosineDistance" in query and "sourcecut.passages" in query:
                self.calls.append((name, arguments))
                text = "The men were weak for want of food on the mountain trail."
                return {
                    "columns": [
                        "passage_id",
                        "author_display_name",
                        "entry_date",
                        "passage_text",
                    ],
                    "rows": [["passage:semantic", "Meriwether Lewis", 18050920, text]],
                }
            if "cosineDistance" in query and "sourcecut.media_assets" in query:
                self.calls.append((name, arguments))
                row = media_row(asset_id="loc:semantic", provider_id="semantic")
                return {"columns": list(row), "rows": [row]}
            return await super().call_tool(name, arguments)

    mcp = SemanticMcp()
    embedder = FakeEmbedder()

    board = asyncio.run(
        ResearchBoardService(mcp, embedder=embedder).build_board("People exhausted by hunger")
    )

    semantic_queries = [
        call[1]["query"] for call in mcp.calls if "cosineDistance" in call[1]["query"]
    ]
    assert semantic_queries
    assert "FROM sourcecut.passages FINAL" in semantic_queries[0]
    assert any("FROM sourcecut.media_assets FINAL" in query for query in semantic_queries)
    citations = [
        citation
        for item in board.evidence_matrix
        for citation in item.evidence
    ]
    assert all("distance" not in citation.model_dump() for citation in citations)
    assert len(embedder.calls) >= 2
    assert "cosineDistance" in _semantic_passage_query((0.25, 0.75))


def test_visual_mismatch_downgrades_metadata_match() -> None:
    requirement = AssetRequirement(
        requirement_id="bitterroot:terrain",
        title="Terrain",
        category="terrain",
        production_need="Mountain terrain",
        search_terms=("bitterroot", "mountain"),
        evidence=(
            EvidenceCitation.model_validate(evidence_row()),
        ),
    )
    asset = MediaAsset.model_validate(
        media_row(
            asset_id="loc:photo",
            provider_id="photo",
            title="Bitterroot mountain reference",
            historical_relationship="LATER_REPRESENTATION",
        )
    )

    verified = verify_asset(
        asset,
        requirement,
        visual_inspection=VisualInspection(
            relevant=False,
            visible_findings="The thumbnail is a portrait with no visible terrain.",
            mismatch_flags=("no terrain visible",),
        ),
    )

    assert verified.confidence is BoardConfidence.UNSUPPORTED
    assert "visual inspection" in verified.why_selected


def test_visual_inspector_rejects_paths_outside_cache(tmp_path: Path) -> None:
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"image")
    asset = MediaAsset.model_validate(
        media_row(thumbnail_path=str(outside), historical_relationship="LATER_REPRESENTATION")
    )
    requirement = AssetRequirement(
        requirement_id="bitterroot:terrain",
        title="Terrain",
        category="terrain",
        production_need="Mountain terrain",
        search_terms=("mountain",),
        evidence=(EvidenceCitation.model_validate(evidence_row()),),
    )
    inspector = GeminiVisualInspector(object(), cache_root=tmp_path / "approved")

    with pytest.raises(ValueError, match="outside the approved LOC cache"):
        asyncio.run(inspector.inspect(asset, requirement))


def test_relationship_and_rights_are_not_overridden_by_metadata_match() -> None:
    requirement = AssetRequirement(
        requirement_id="bitterroot:terrain",
        title="Terrain",
        category="terrain",
        production_need="Mountain terrain",
        search_terms=("mountain",),
        evidence=(EvidenceCitation.model_validate(evidence_row()),),
    )
    restricted = MediaAsset.model_validate(media_row(rights_status=RightsStatus.RESTRICTED))
    later = MediaAsset.model_validate(
        media_row(historical_relationship=HistoricalRelationship.LATER_REPRESENTATION)
    )

    assert verify_asset(restricted, requirement).confidence is BoardConfidence.RIGHTS_REJECTED
    assert verify_asset(later, requirement).confidence is BoardConfidence.INTERPRETIVE


class PassageFallbackMcp:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        assert name == "run_query"
        query = arguments["query"]
        self.queries.append(query)
        if "sourcecut.author_date_matrix" in query:
            return {
                "columns": [
                    "author_id",
                    "author_display_name",
                    "entry_date",
                    "mention_count",
                    "observation_count",
                    "passage_ids",
                ],
                "rows": [["clark", "William Clark", 18050916, 1, 0, ["passage:1"]]],
            }
        if "sourcecut.route_waypoints" in query:
            return {
                "columns": [
                    "waypoint_id",
                    "entry_date",
                    "name",
                    "lat",
                    "lon",
                    "citation_passage_ids",
                    "source_note",
                ],
                "rows": [
                    [
                        "lolo-pass",
                        18050916,
                        "Lolo Pass",
                        46.635,
                        -114.58,
                        ["passage:1"],
                        "NPS",
                    ]
                ],
            }
        if query == EVIDENCE_QUERY:
            return {"columns": ["observation_id"], "rows": []}
        if query == PASSAGE_EVIDENCE_QUERY:
            text = "The road was steep and the horses struggled through snow."
            return {
                "columns": [
                    "passage_id",
                    "author_display_name",
                    "entry_date",
                    "passage_text",
                ],
                "rows": [["passage:1", "William Clark", 18050916, text]],
            }
        row = media_row()
        return {"columns": list(row), "rows": [row]}


def test_passage_fallback_uses_exact_mcp_text_when_observations_are_empty() -> None:
    mcp = PassageFallbackMcp()
    events: list[tuple[str, dict[str, Any]]] = []

    def sink(
        event_type: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any],
        duration_ms: int,
    ) -> None:
        del stage, status, message, duration_ms
        events.append((event_type, payload))

    board = asyncio.run(
        ResearchBoardService(mcp, event_sink=sink).build_board(
            "Build the Bitterroot board"
        )
    )

    assert mcp.queries[0:2] == [EVIDENCE_QUERY, PASSAGE_EVIDENCE_QUERY]
    assert any("author_date_matrix" in query for query in mcp.queries)
    assert MEDIA_QUERY in mcp.queries
    assert "sourcecut.route_waypoints" in mcp.queries[-1]
    assert board.evidence_matrix
    citations = [
        citation
        for requirement in board.evidence_matrix
        for citation in requirement.evidence
    ]
    assert all(citation.passage_id == "passage:1" for citation in citations)
    passage = "The road was steep and the horses struggled through snow."
    assert all(citation.source_quote in passage for citation in citations)
    assert any(citation.canonical_term == "snow" for citation in citations)
    assert [event_type for event_type, _ in events].count("fallback") == 1
    tool_events = [payload for event_type, payload in events if event_type == "mcp_tool_call"]
    assert len(tool_events) >= 3
    assert tool_events[1]["row_count"] == 1
    assert all("source_quote" not in payload for payload in tool_events)


def test_visual_failure_keeps_board_available_and_warns() -> None:
    board = asyncio.run(
        ResearchBoardService(
            FakeMcpClient(),
            visual_inspector=FailingInspector(),
            visual_inspection_limit=1,
        ).build_board("Build the Bitterroot board")
    )

    assert board.sections
    assert any("visual inspections failed" in warning for warning in board.warnings)
    assert any(
        item.confidence is BoardConfidence.INTERPRETIVE
        for item in board.reviewed_assets
    )
