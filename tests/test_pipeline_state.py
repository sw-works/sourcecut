from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sourcecut_api.corpora import create_corpus_registry
from sourcecut_api.main import create_app
from sourcecut_api.services.pipeline_state import build_corpus_pipeline, list_pipelines

LEWIS_COUNTS = {
    "passages": 2384,
    "authors": 3,
    "entries": 2267,
    "observations": 14685,
    "terms": 5546,
    "media_assets": 22,
    "route_waypoints": 9,
}
ODYSSEY_COUNTS = {
    "text_units": 15570,
    "tokens": 87189,
    "passages": 1048,
    "formula_occurrences": 80091,
    "narrative_events": 39,
    "places": 16,
    "route_hypotheses": 3,
    "media_assets": 5,
    "claims": 0,
}


class FakePipelineMcp:
    def __init__(self, counts: dict[str, dict[str, int]]) -> None:
        self.counts = counts
        self.asked: list[str] = []

    async def get_corpus_pipeline_counts(self, corpus_id: str) -> dict[str, int]:
        self.asked.append(corpus_id)
        return self.counts.get(corpus_id, {})


def test_both_corpora_report_the_same_steps_in_their_own_nouns() -> None:
    registry = create_corpus_registry()
    pipelines = list_pipelines(
        registry,
        {"lewis-and-clark": LEWIS_COUNTS, "odyssey": ODYSSEY_COUNTS},
        example_dir=Path("data/examples"),
    )

    assert [pipeline.corpus_id for pipeline in pipelines] == ["lewis-and-clark", "odyssey"]
    steps = {pipeline.corpus_id: [stage.key for stage in pipeline.stages] for pipeline in pipelines}
    assert steps["lewis-and-clark"] == steps["odyssey"]

    lewis = next(item for item in pipelines if item.corpus_id == "lewis-and-clark")
    odyssey = next(item for item in pipelines if item.corpus_id == "odyssey")
    lewis_parse = dict(next(s for s in lewis.stages if s.key == "parse").counts)
    odyssey_parse = dict(next(s for s in odyssey.stages if s.key == "parse").counts)
    # The journals are addressed by dated entry, the poem by line: same step,
    # different nouns, and neither is renamed to match the other.
    assert "entries" in lewis_parse and "lines" in odyssey_parse


def test_an_unpopulated_layer_reports_partial_rather_than_complete() -> None:
    registry = create_corpus_registry()
    detail = registry.get("odyssey")
    assert detail is not None

    pipeline = build_corpus_pipeline(detail, ODYSSEY_COUNTS)
    extract = next(stage for stage in pipeline.stages if stage.key == "extract")

    assert extract.state == "partial"
    assert dict(extract.counts)["reviewed claims"] == 0


def test_a_corpus_with_no_counts_still_reports_its_sources_and_rights() -> None:
    registry = create_corpus_registry()
    detail = registry.get("lewis-and-clark")
    assert detail is not None

    pipeline = build_corpus_pipeline(detail, {})

    assert pipeline.licenses == ("Public domain in the United States",)
    assert len(pipeline.sources) == 2
    assert all(stage.state == "empty" for stage in pipeline.stages if stage.key != "acquire")


def test_windows_link_only_where_a_board_was_captured(tmp_path: Path) -> None:
    """A window with no committed capture is named but not linked."""
    from sourcecut_api.agents.planner import load_scopes

    registry = create_corpus_registry()
    detail = registry.get("lewis-and-clark")
    assert detail is not None
    scopes = load_scopes()
    (tmp_path / f"{scopes[0].scope_id}.json").write_text("{}", encoding="utf-8")

    pipeline = build_corpus_pipeline(detail, LEWIS_COUNTS, scopes=scopes, example_dir=tmp_path)

    captured = [window for window in pipeline.windows if window.captured]
    assert [window.scope_id for window in captured] == [scopes[0].scope_id]


def test_the_pipelines_route_answers_from_the_read_only_client() -> None:
    app = create_app(session_repository=object())
    fake = FakePipelineMcp({"lewis-and-clark": LEWIS_COUNTS, "odyssey": ODYSSEY_COUNTS})
    app.state.mcp_client_factory = lambda: fake

    with TestClient(app) as client:
        response = client.get("/api/v1/pipelines")

    assert response.status_code == 200
    body: list[dict[str, Any]] = response.json()
    assert {item["corpus_id"] for item in body} == {"lewis-and-clark", "odyssey"}
    assert fake.asked == ["lewis-and-clark", "odyssey"]


def test_the_route_survives_a_database_that_will_not_answer() -> None:
    """The page still says what the corpora are when the counts cannot be read."""

    class BrokenMcp:
        async def get_corpus_pipeline_counts(self, corpus_id: str) -> dict[str, int]:
            raise RuntimeError("ClickHouse is unreachable")

    app = create_app(session_repository=object())
    app.state.mcp_client_factory = BrokenMcp

    with TestClient(app) as client:
        response = client.get("/api/v1/pipelines")

    assert response.status_code == 200
    assert all(item["sources"] for item in response.json())
