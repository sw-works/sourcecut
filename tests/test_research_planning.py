from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from sourcecut_api.agents.planner import (
    BASELINE_REQUIREMENTS,
    GeminiResearchPlanner,
    PlanValidationError,
    ResearchPlanDraft,
    StaticResearchPlanner,
    build_plan,
    default_scope,
    load_scopes,
    normalize_terms,
    route_scope,
)
from sourcecut_api.models import AssetRequirement, EvidenceCitation
from sourcecut_api.models.plan import CoverageEntry, PlannedRequirement, ResearchPlan
from sourcecut_api.services.board import (
    ResearchBoardService,
    evaluate_coverage,
    gap_passage_query,
)


def plan(**changes: Any) -> ResearchPlan:
    values: dict[str, Any] = {
        "scope_id": "bitterroot-september-1805",
        "title": "Crossing the Bitterroots — September 1805",
        "window_start": 18050909,
        "window_end": 18050930,
        "rationale": "Testing.",
        "requirements": (
            PlannedRequirement(
                category="weather",
                title="Weather",
                production_need="Weather references.",
                search_terms=("snow",),
                success_criteria="Two authors describe weather.",
            ),
        ),
        "planner": "test",
        "prompt_version": "research-plan-v1",
    }
    values.update(changes)
    return ResearchPlan(**values)


def citation(author: str, category: str = "weather") -> EvidenceCitation:
    return EvidenceCitation(
        observation_id=f"observation:{author}:{category}",
        passage_id=f"passage:{author}",
        author_display_name=author,
        entry_date=18050916,
        category=category,
        canonical_term="snow",
        source_quote="the mountains were covered with snow",
        confidence=0.9,
    )


def requirement(citations: tuple[EvidenceCitation, ...]) -> AssetRequirement:
    return AssetRequirement(
        requirement_id="bitterroot-september-1805:weather",
        title="Weather",
        category="weather",
        production_need="Weather references.",
        search_terms=("snow",),
        evidence=citations,
    )


def test_routing_prefers_the_longest_matching_scope_phrase() -> None:
    scopes = load_scopes()

    assert route_scope("the Great Falls portage", scopes).scope_id == (
        "great-falls-portage-1805"
    )
    assert route_scope("winter at Fort Clatsop", scopes).scope_id == (
        "fort-clatsop-winter-1805"
    )
    # No keyword match falls back to the default scope rather than guessing.
    assert route_scope("something else entirely", scopes) == default_scope(scopes)


def test_plan_window_comes_from_the_scope_not_the_model() -> None:
    draft = ResearchPlanDraft(
        scope_id="great-falls-portage-1805",
        rationale="The brief describes the portage.",
        requirements=[
            {
                "category": "terrain",
                "title": "Portage terrain",
                "production_need": "Terrain references.",
                "search_terms": ["portage", "falls"],
                "success_criteria": "Two authors describe the portage.",
            }
        ],
    )

    built = build_plan(draft, planner="gemini:test")

    scope = next(
        item for item in load_scopes() if item.scope_id == "great-falls-portage-1805"
    )
    assert built.window_start == scope.window_start
    assert built.window_end == scope.window_end
    assert built.title == scope.title


def test_plan_rejects_an_unknown_scope() -> None:
    draft = ResearchPlanDraft(
        scope_id="invented-scope",
        rationale="Nope.",
        requirements=[
            {
                "category": "weather",
                "title": "Weather",
                "production_need": "Weather references.",
                "search_terms": ["snow"],
                "success_criteria": "Two authors.",
            }
        ],
    )

    with pytest.raises(PlanValidationError, match="Unknown scope_id"):
        build_plan(draft, planner="gemini:test")


def test_plan_drops_unsafe_terms_and_duplicate_categories() -> None:
    draft = ResearchPlanDraft(
        scope_id="bitterroot-september-1805",
        rationale="Testing term hygiene.",
        requirements=[
            {
                "category": "weather",
                "title": "Weather",
                "production_need": "Weather references.",
                "search_terms": ["Snow", "snow", "'; DROP TABLE passages --", "cold"],
                "success_criteria": "Two authors.",
            },
            {
                "category": "weather",
                "title": "Duplicate weather",
                "production_need": "Ignored.",
                "search_terms": ["rain"],
                "success_criteria": "Ignored.",
            },
        ],
    )

    built = build_plan(draft, planner="gemini:test")

    assert len(built.requirements) == 1
    assert built.requirements[0].search_terms == ("snow", "cold")


def test_plan_requires_at_least_one_usable_term() -> None:
    draft = ResearchPlanDraft(
        scope_id="bitterroot-september-1805",
        rationale="Testing.",
        requirements=[
            {
                "category": "weather",
                "title": "Weather",
                "production_need": "Weather references.",
                "search_terms": ["!!!", "   "],
                "success_criteria": "Two authors.",
            }
        ],
    )

    with pytest.raises(PlanValidationError, match="no usable search terms"):
        build_plan(draft, planner="gemini:test")


def test_normalize_terms_is_case_folding_and_deduplicating() -> None:
    assert normalize_terms(["Snow", "SNOW", " snow ", "x"], 5) == ("snow",)


class BrokenPlannerClient:
    """Stands in for a model that returns something unusable."""

    def __init__(self) -> None:
        self.models = self

    def generate_content(self, **kwargs: Any) -> Any:
        del kwargs
        raise RuntimeError("planner unavailable")


def test_model_planner_falls_back_to_routing_when_the_model_fails() -> None:
    planner = GeminiResearchPlanner(BrokenPlannerClient(), model="gemini-test")

    result = asyncio.run(planner.plan("the Great Falls portage of the Missouri"))

    assert result.scope_id == "great-falls-portage-1805"
    assert result.requirements == BASELINE_REQUIREMENTS
    assert "Model planning failed" in result.rationale


def test_static_gap_expansion_only_offers_terms_not_already_searched() -> None:
    current = plan()
    gaps = (
        CoverageEntry(
            requirement_id="bitterroot-september-1805:weather",
            category="weather",
            status="unmet",
            evidence_count=0,
            author_count=0,
            minimum_authors=2,
            success_criteria="Two authors describe weather.",
        ),
    )

    widened = asyncio.run(StaticResearchPlanner().expand_gaps("prompt", current, gaps))

    assert "weather" in widened
    assert "snow" not in widened["weather"]


def test_coverage_grades_each_requirement_against_its_own_criterion() -> None:
    current = plan()

    unmet = evaluate_coverage((), current)
    assert [entry.status for entry in unmet.entries] == ["unmet"]
    assert unmet.gaps == unmet.entries

    single = evaluate_coverage((requirement((citation("William Clark"),)),), current)
    assert [entry.status for entry in single.entries] == ["single_source"]

    met = evaluate_coverage(
        (requirement((citation("William Clark"), citation("Patrick Gass"))),), current
    )
    assert [entry.status for entry in met.entries] == ["met"]
    assert met.gaps == ()
    assert met.met_count == 1


def test_gap_query_matches_whole_tokens_inside_the_plan_window() -> None:
    query = gap_passage_query(18050909, 18050930, ["mockersons", "a"])

    assert "entry_date BETWEEN 18050909 AND 18050930" in query
    # hasAnyTokens takes the whole array; hasToken cannot, because its second
    # argument must be constant and a lambda variable is not.
    assert "hasAnyTokens(lower(passage_text), [" in query
    assert "'mockersons'" in query
    # Single characters are not usable tokens and must not reach the literal.
    assert "'a'" not in query

    with pytest.raises(ValueError, match="at least one usable token"):
        gap_passage_query(18050909, 18050930, ["!!"])


class GapClosingMcp:
    """Returns nothing for the first pass and a passage once the search widens."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        assert name == "run_query"
        query = arguments["query"]
        self.queries.append(query)
        if "hasAnyTokens" in query and "mockersons" in query:
            return {
                "columns": [
                    "passage_id",
                    "author_display_name",
                    "entry_date",
                    "passage_text",
                ],
                "rows": [
                    [
                        "passage:gass",
                        "Patrick Gass",
                        18050916,
                        "the men made mockersons of green hides",
                    ]
                ],
            }
        if "hasAnyTokens" in query:
            return {
                "columns": [
                    "passage_id",
                    "author_display_name",
                    "entry_date",
                    "passage_text",
                ],
                "rows": [],
            }
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
                "rows": [],
            }
        if "sourcecut.route_waypoints" in query:
            return {"columns": ["waypoint_id"], "rows": []}
        if "sourcecut.media_assets" in query:
            return {"columns": ["asset_id"], "rows": []}
        return {"columns": ["observation_id"], "rows": []}


class GapPlanner:
    """Plans one equipment requirement and widens it with a period spelling."""

    name = "test"

    async def plan(self, prompt: str) -> ResearchPlan:
        del prompt
        return plan(
            requirements=(
                PlannedRequirement(
                    category="equipment",
                    title="Clothing and equipment",
                    production_need="Clothing references.",
                    search_terms=("clothing",),
                    success_criteria="One author describes clothing.",
                    minimum_authors=1,
                ),
            )
        )

    async def expand_gaps(
        self, prompt: str, current: ResearchPlan, gaps: Any
    ) -> dict[str, tuple[str, ...]]:
        del prompt, current, gaps
        return {"equipment": ("mockersons",)}


class RecordingMemory:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, tuple[str, ...]]] = []

    def record_discovered_terms(
        self, category: str, term: str, expansions: Any
    ) -> None:
        self.records.append((category, term, tuple(expansions)))


def test_coverage_loop_widens_the_search_and_remembers_what_worked() -> None:
    mcp = GapClosingMcp()
    memory = RecordingMemory()
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
        ResearchBoardService(
            mcp, event_sink=sink, planner=GapPlanner(), memory=memory
        ).build_board("Clothing on the Bitterroot crossing")
    )

    kinds = [event_type for event_type, _ in events]
    assert kinds.count("plan_created") == 1
    assert kinds.count("gap_replan") == 1
    # Coverage is reported before and after the extra round.
    assert kinds.count("coverage_evaluated") == 2
    assert kinds.count("memory_updated") == 1

    assert memory.records == [("equipment", "clothing", ("mockersons",))]
    assert board.coverage is not None
    assert board.coverage.rounds == 2
    assert [entry.status for entry in board.coverage.entries] == ["met"]
    assert board.plan is not None
    assert "mockersons" in board.plan.requirements[0].search_terms
    quotes = [
        item.source_quote
        for req in board.evidence_matrix
        for item in req.evidence
    ]
    assert any("mockersons" in quote for quote in quotes)


def test_coverage_loop_stops_when_widening_finds_nothing() -> None:
    class EmptyGapPlanner(GapPlanner):
        async def expand_gaps(
            self, prompt: str, current: ResearchPlan, gaps: Any
        ) -> dict[str, tuple[str, ...]]:
            del prompt, current, gaps
            return {"equipment": ("nonexistentword",)}

    mcp = GapClosingMcp()
    memory = RecordingMemory()

    board = asyncio.run(
        ResearchBoardService(
            mcp, planner=EmptyGapPlanner(), memory=memory
        ).build_board("Clothing on the Bitterroot crossing")
    )

    assert memory.records == []
    assert board.coverage is not None
    assert board.coverage.rounds == 2
    assert [entry.status for entry in board.coverage.entries] == ["unmet"]


def test_research_rounds_can_be_capped_at_one() -> None:
    mcp = GapClosingMcp()

    board = asyncio.run(
        ResearchBoardService(
            mcp, planner=GapPlanner(), max_research_rounds=1
        ).build_board("Clothing on the Bitterroot crossing")
    )

    assert not any("hasAnyTokens" in query for query in mcp.queries)
    assert board.coverage is not None
    assert board.coverage.rounds == 1


def test_a_plan_at_the_cap_validates_and_one_term_past_it_does_not() -> None:
    """A board that fails validation on re-read 500s on its own permalink.

    The first live run produced exactly that: the widening round appended
    curated vocabulary to five requirements and pushed four of them past the
    plan model's cap, so the board was written and then could not be read back.
    """
    from sourcecut_api.models.plan import MAX_SEARCH_TERMS, PlannedRequirement

    fields = {
        "category": "transportation",
        "title": "Transport",
        "production_need": "What the party rode and carried",
        "success_criteria": "Two authors agree",
    }

    at_cap = PlannedRequirement(
        **fields, search_terms=tuple(f"term{index}" for index in range(MAX_SEARCH_TERMS))
    )
    assert len(at_cap.search_terms) == MAX_SEARCH_TERMS

    with pytest.raises(ValidationError):
        PlannedRequirement(
            **fields,
            search_terms=tuple(f"term{index}" for index in range(MAX_SEARCH_TERMS + 1)),
        )
