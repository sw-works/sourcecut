from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import mimetypes
import os
import re
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from google.genai import types

from sourcecut_api.agents.planner import (
    BASELINE_REQUIREMENTS,
    ResearchPlanner,
    StaticResearchPlanner,
    create_planner,
)
from sourcecut_api.constants import BITTERROOT_END, BITTERROOT_START, window_dates
from sourcecut_api.integrations.clickhouse_mcp import ClickHouseMcpClient, ClickHouseMcpSettings
from sourcecut_api.integrations.genai import GenaiSettings, create_genai_client
from sourcecut_api.models import (
    AgreementCell,
    AssetRequirement,
    BoardConfidence,
    BoardMediaAsset,
    BoardSection,
    EvidenceCitation,
    HistoricalRelationship,
    MediaAsset,
    ResearchBoard,
    RightsStatus,
    RouteWaypoint,
    VerifiedAsset,
    VisualInspection,
)
from sourcecut_api.models.plan import (
    MAX_SEARCH_TERMS,
    CoverageEntry,
    CoverageReport,
    ResearchPlan,
)
from sourcecut_api.telemetry import sanitize_sql

DEFAULT_MODEL = "gemini-2.5-flash"
REUSABLE_RIGHTS = {
    RightsStatus.PUBLIC_DOMAIN,
    RightsStatus.CC0,
    RightsStatus.REUSABLE_WITH_CONDITIONS,
}
STOP_WORDS = {
    "and",
    "for",
    "from",
    "historical",
    "image",
    "lewis",
    "reference",
    "the",
    "visual",
    "with",
}

EVIDENCE_QUERY = f"""
SELECT
    observation_id,
    passage_id,
    author_display_name,
    entry_date,
    category,
    canonical_term,
    source_quote,
    confidence
FROM sourcecut.evidence_window(
    start={BITTERROOT_START},
    end={BITTERROOT_END},
    limit=200
)
""".strip()

MEDIA_QUERY = """
SELECT
    asset_id,
    provider,
    provider_id,
    title,
    description,
    creators,
    asset_type,
    creation_date_text,
    creation_year,
    subjects,
    places,
    source_url,
    media_url,
    thumbnail_path,
    rights_status,
    rights_text,
    historical_relationship,
    raw_metadata,
    metadata_sha256
FROM sourcecut.media_assets FINAL
ORDER BY provider, rights_status, asset_type, creation_year, asset_id
LIMIT 200
""".strip()

PASSAGE_EVIDENCE_QUERY = f"""
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN {BITTERROOT_START} AND {BITTERROOT_END}
ORDER BY entry_date, author_id, passage_id
LIMIT 200
""".strip()


def evidence_query(start: int, end: int) -> str:
    """Validated observation evidence for one plan window."""
    return f"""
SELECT
    observation_id,
    passage_id,
    author_display_name,
    entry_date,
    category,
    canonical_term,
    source_quote,
    confidence
FROM sourcecut.evidence_window(
    start={int(start)},
    end={int(end)},
    limit=200
)
""".strip()


def passage_evidence_query(start: int, end: int) -> str:
    return f"""
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN {int(start)} AND {int(end)}
ORDER BY entry_date, author_id, passage_id
LIMIT 200
""".strip()


def gap_passage_query(start: int, end: int, terms: Sequence[str]) -> str:
    """Targeted passage search for one requirement's widened vocabulary.

    Used by the coverage loop's second round; matches whole tokens so it
    stays consistent with the rest of the retrieval layer.
    """
    tokens = tuple(
        dict.fromkeys(
            token
            for term in terms
            for token in re.findall(r"[a-z0-9]+", term.casefold())
            if len(token) >= 3
        )
    )
    if not tokens:
        raise ValueError("gap search requires at least one usable token")
    literal = "[" + ",".join(f"'{token}'" for token in tokens) + "]"
    # hasAnyTokens, not arrayExists(t -> hasToken(..., t), [...]): hasToken
    # requires its second argument to be constant, so the lambda form is
    # rejected by ClickHouse at execution time with code 44. This is the same
    # function 067_author_date_matrix_any_tokens.sql already uses.
    return f"""
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN {int(start)} AND {int(end)}
  AND hasAnyTokens(lower(passage_text), {literal})
ORDER BY entry_date, author_id, passage_id
LIMIT 60
""".strip()

VISUAL_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["relevant", "visible_findings", "mismatch_flags"],
    properties={
        "relevant": types.Schema(type=types.Type.BOOLEAN),
        "visible_findings": types.Schema(type=types.Type.STRING),
        "mismatch_flags": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
        ),
    },
)


class RuntimeMcpClient(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class VisualInspector(Protocol):
    async def inspect(
        self,
        asset: MediaAsset,
        requirement: AssetRequirement,
    ) -> VisualInspection: ...


EventSink = Callable[[str, str, str, str, dict[str, Any], int], None]


class QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> tuple[float, ...]: ...


class ResearchMemory(Protocol):
    """Sink for retrieval vocabulary that a gap round proved useful.

    Curated reference data only (ADR-017) — never evidence.
    """

    def record_discovered_terms(
        self, category: str, term: str, expansions: Sequence[str]
    ) -> None: ...


class GeminiVisualInspector:
    def __init__(
        self,
        client: Any,
        *,
        model: str = DEFAULT_MODEL,
        cache_root: Path = Path("data/archive-cache/loc"),
    ) -> None:
        self._client = client
        self._model = model
        self._cache_root = cache_root.resolve()

    async def inspect(
        self,
        asset: MediaAsset,
        requirement: AssetRequirement,
    ) -> VisualInspection:
        image_path = Path(asset.thumbnail_path).resolve()
        if not image_path.is_relative_to(self._cache_root):
            raise ValueError("Thumbnail path is outside the approved LOC cache")
        if not image_path.is_file():
            raise ValueError(f"Cached thumbnail is missing: {asset.thumbnail_path}")
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        prompt = (
            "Inspect only what is visibly present in this archival thumbnail. "
            "Do not infer ownership, date, location, or historical provenance from appearance.\n"
            f"Requirement: {requirement.production_need}\n"
            f"Catalog title: {asset.title}\n"
            "Mark relevant only when visible features help the stated production requirement."
        )

        def generate() -> Any:
            return self._client.models.generate_content(
                model=self._model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_path.read_bytes(), mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=VISUAL_RESPONSE_SCHEMA,
                ),
            )

        response = await asyncio.to_thread(generate)
        if isinstance(response.parsed, VisualInspection):
            return response.parsed
        if response.parsed is not None:
            return VisualInspection.model_validate(response.parsed)
        if response.text is None:
            raise ValueError("Gemini returned no visual inspection")
        return VisualInspection.model_validate_json(response.text)


class ResearchBoardService:
    def __init__(
        self,
        mcp_client: RuntimeMcpClient,
        *,
        visual_inspector: VisualInspector | None = None,
        visual_inspection_limit: int = 2,
        event_sink: EventSink | None = None,
        embedder: QueryEmbedder | None = None,
        planner: ResearchPlanner | None = None,
        max_research_rounds: int = 2,
        memory: ResearchMemory | None = None,
    ) -> None:
        self._mcp = mcp_client
        self._visual_inspector = visual_inspector
        self._visual_inspection_limit = visual_inspection_limit
        self.event_sink = event_sink
        self._embedder = embedder
        self._planner: ResearchPlanner = planner or StaticResearchPlanner()
        self._max_research_rounds = max(1, min(3, max_research_rounds))
        self._memory = memory
        self._query_vectors: dict[str, tuple[float, ...]] = {}

    async def build_board(self, prompt: str) -> ResearchBoard:
        plan = await self._planner.plan(prompt)
        self._emit(
            "plan_created",
            "planning",
            "complete",
            f"Planned {len(plan.requirements)} requirement(s) over {plan.title}.",
            {
                "planner": plan.planner,
                "scope_id": plan.scope_id,
                "window_start": plan.window_start,
                "window_end": plan.window_end,
                "rationale": plan.rationale,
                "categories": [item.category for item in plan.requirements],
            },
        )

        evidence = await self._load_evidence(prompt, plan)
        requirements = build_asset_requirements(evidence, plan)
        coverage = evaluate_coverage(requirements, plan)
        plan, evidence, requirements, coverage = await self._close_coverage_gaps(
            prompt, plan, evidence, requirements, coverage
        )

        requirements, assets, route_waypoints = await asyncio.gather(
            self._with_agreement_all(requirements, plan),
            self._load_media_assets(),
            self._load_route(evidence, plan),
        )
        reviewed: list[VerifiedAsset] = []
        sections: list[BoardSection] = []
        inspected = 0
        inspection_failures = 0

        for requirement in requirements:
            ranked = await self._rank_assets(requirement, assets)
            requirement_reviews: list[VerifiedAsset] = []
            for asset in ranked[:5]:
                inspection = None
                initial = verify_asset(asset, requirement)
                if (
                    initial.confidence is BoardConfidence.INTERPRETIVE
                    and self._visual_inspector is not None
                    and asset.thumbnail_path
                    and inspected < self._visual_inspection_limit
                ):
                    try:
                        inspection = await self._visual_inspector.inspect(asset, requirement)
                    except Exception:
                        inspection_failures += 1
                    inspected += 1
                verified = verify_asset(asset, requirement, visual_inspection=inspection)
                requirement_reviews.append(verified)
                reviewed.append(verified)

            selected = tuple(
                item
                for item in requirement_reviews
                if item.confidence
                in {
                    BoardConfidence.HIGH,
                    BoardConfidence.SINGLE_SOURCE,
                    BoardConfidence.INTERPRETIVE,
                }
            )[:3]
            if selected:
                sections.append(BoardSection(title=requirement.title, assets=selected))

        warnings = _warnings(reviewed, requirements, assets, inspection_failures)
        self._emit(
            "verification_completed",
            "verification",
            "complete",
            "Archive candidates passed rights and visual verification.",
            {
                "reviewed_count": len(reviewed),
                "inspection_count": inspected,
                "failure_count": inspection_failures,
            },
        )
        authors = sorted({citation.author_display_name for citation in evidence})
        return ResearchBoard(
            prompt=prompt,
            title=plan.title,
            summary=(
                f"Evidence-derived board with {len(requirements)} requirements, "
                f"{sum(len(section.assets) for section in sections)} selected asset references, "
                f"and exact passage drill-down. "
                f"{coverage.met_count} of {len(coverage.entries)} planned requirements met "
                f"their evidence criteria after {coverage.rounds} research round(s)."
            ),
            evidence_matrix=requirements,
            sections=tuple(sections),
            reviewed_assets=tuple(reviewed),
            warnings=warnings,
            sources_used=("Library of Congress", *authors),
            route_waypoints=route_waypoints,
            plan=plan,
            coverage=coverage,
        )

    async def _close_coverage_gaps(
        self,
        prompt: str,
        plan: ResearchPlan,
        evidence: tuple[EvidenceCitation, ...],
        requirements: tuple[AssetRequirement, ...],
        coverage: CoverageReport,
    ) -> tuple[
        ResearchPlan,
        tuple[EvidenceCitation, ...],
        tuple[AssetRequirement, ...],
        CoverageReport,
    ]:
        """Goal-directed second pass over the requirements evidence did not satisfy.

        Bounded by ``max_research_rounds``. Each round widens the search
        vocabulary for unmet requirements only, re-queries passages inside the
        same plan window, and recomputes coverage. Gap evidence is
        passage-derived and carries ``passage-term:`` citation ids, so it stays
        distinguishable from validated observations.
        """
        self._emit_coverage(coverage, plan)
        rounds = 1
        while rounds < self._max_research_rounds and coverage.gaps:
            gaps = coverage.gaps
            widened = await self._planner.expand_gaps(prompt, plan, gaps)
            if not widened:
                break
            self._emit(
                "gap_replan",
                "planning",
                "active",
                f"Widening the search for {len(widened)} unmet requirement(s).",
                {
                    "round": rounds + 1,
                    "categories": sorted(widened),
                    "terms": {category: list(terms) for category, terms in widened.items()},
                },
            )
            found = await self._search_gaps(plan, widened)
            rounds += 1
            if not found:
                coverage = coverage.model_copy(update={"rounds": rounds})
                self._emit_coverage(coverage, plan)
                break
            plan = plan.with_requirements(
                tuple(
                    requirement.model_copy(
                        update={
                            # Bounded: widening may not grow the term list past
                            # what the plan model accepts, or the finished board
                            # fails validation when it is read back.
                            "search_terms": tuple(
                                dict.fromkeys(
                                    (
                                        *requirement.search_terms,
                                        *widened.get(requirement.category, ()),
                                    )
                                )
                            )[:MAX_SEARCH_TERMS]
                        }
                    )
                    if requirement.category in widened
                    else requirement
                    for requirement in plan.requirements
                )
            )
            evidence = _unique_citations((*evidence, *found))
            requirements = build_asset_requirements(evidence, plan)
            coverage = evaluate_coverage(requirements, plan).model_copy(
                update={"rounds": rounds}
            )
            self._emit_coverage(coverage, plan)
            self._remember(plan, widened, found)
        return plan, evidence, requirements, coverage

    async def _search_gaps(
        self, plan: ResearchPlan, widened: Mapping[str, Sequence[str]]
    ) -> tuple[EvidenceCitation, ...]:
        found: list[EvidenceCitation] = []
        for category, terms in sorted(widened.items()):
            try:
                query = gap_passage_query(plan.window_start, plan.window_end, terms)
            except ValueError:
                continue
            columns, rows = await self._run_query(query, f"gap_{category}")
            found.extend(
                _derive_passage_evidence(
                    rows, columns, categories={category: tuple(terms)}
                )
            )
        return tuple(found)

    def _remember(
        self,
        plan: ResearchPlan,
        widened: Mapping[str, Sequence[str]],
        found: Sequence[EvidenceCitation],
    ) -> None:
        if self._memory is None or not found:
            return
        productive = {citation.category for citation in found}
        for category, terms in sorted(widened.items()):
            if category not in productive:
                continue
            seed = next(
                (
                    requirement.search_terms[0]
                    for requirement in plan.requirements
                    if requirement.category == category and requirement.search_terms
                ),
                category,
            )
            try:
                self._memory.record_discovered_terms(category, seed, tuple(terms))
            except Exception as error:
                # Vocabulary memory is an optimization; never fail a board for
                # it. Say why it failed, though: swallowing the reason turned a
                # missing ClickHouse grant into an unexplained red line on the
                # live timeline with nothing in the logs to work from.
                self._emit(
                    "memory_write_failed",
                    "memory",
                    "failed",
                    f"Discovered retrieval vocabulary could not be persisted: {error}"[:400],
                    {"category": category, "error_type": type(error).__name__},
                )
                continue
            self._emit(
                "memory_updated",
                "memory",
                "complete",
                f"Recorded {len(terms)} discovered search term(s) for {category}.",
                {"category": category, "terms": list(terms)},
            )

    def _emit_coverage(self, coverage: CoverageReport, plan: ResearchPlan) -> None:
        self._emit(
            "coverage_evaluated",
            "coverage",
            "complete" if not coverage.gaps else "active",
            (
                f"{coverage.met_count} of {len(coverage.entries)} requirement(s) met "
                f"after round {coverage.rounds}."
            ),
            {
                "round": coverage.rounds,
                "met": coverage.met_count,
                "total": len(coverage.entries),
                "scope_id": plan.scope_id,
                "gaps": [
                    {
                        "category": entry.category,
                        "status": entry.status,
                        "evidence_count": entry.evidence_count,
                        "author_count": entry.author_count,
                    }
                    for entry in coverage.gaps
                ],
            },
        )

    async def _load_evidence(
        self, prompt: str, plan: ResearchPlan
    ) -> tuple[EvidenceCitation, ...]:
        columns, rows = await self._run_query(
            evidence_query(plan.window_start, plan.window_end), "evidence"
        )
        observations = tuple(
            EvidenceCitation(
                observation_id=str(_field(row, columns, "observation_id")),
                passage_id=str(_field(row, columns, "passage_id")),
                author_display_name=str(_field(row, columns, "author_display_name")),
                entry_date=int(_field(row, columns, "entry_date")),
                category=str(_field(row, columns, "category")),
                canonical_term=str(_field(row, columns, "canonical_term")),
                source_quote=str(_field(row, columns, "source_quote")),
                confidence=float(_field(row, columns, "confidence")),
            )
            for row in rows
        )
        semantic_rows: list[Any] = []
        semantic_columns: list[str] = []
        if self._embedder is not None:
            vector = await asyncio.to_thread(self._embedder.embed_query, prompt)
            semantic_columns, semantic_rows = await self._run_query(
                _semantic_passage_query(vector, plan.window_start, plan.window_end),
                "semantic_evidence",
            )
        semantic_evidence = _derive_passage_evidence(semantic_rows, semantic_columns)
        if observations:
            return _unique_citations((*observations, *semantic_evidence))
        self._emit(
            "fallback",
            "evidence",
            "active",
            "Validated observations were empty; passage-level evidence fallback activated.",
            {"reason": "no_validated_observations"},
        )
        passage_columns, passage_rows = await self._run_query(
            passage_evidence_query(plan.window_start, plan.window_end),
            "evidence_fallback",
        )
        fallback = _derive_passage_evidence(passage_rows, passage_columns)
        return _unique_citations((*semantic_evidence, *fallback))

    async def _load_media_assets(self) -> tuple[MediaAsset, ...]:
        columns, rows = await self._run_query(MEDIA_QUERY, "media")
        return tuple(_media_asset(row, columns) for row in rows)

    async def _load_route(
        self, evidence: Sequence[EvidenceCitation], plan: ResearchPlan
    ) -> tuple[RouteWaypoint, ...]:
        query = f"""
SELECT waypoint_id, entry_date, name, lat, lon, citation_passage_ids, source_note
FROM sourcecut.route_waypoints FINAL
WHERE entry_date BETWEEN {plan.window_start} AND {plan.window_end}
ORDER BY entry_date, waypoint_id
LIMIT 50
""".strip()
        columns, rows = await self._run_query(query, "route")
        counts: defaultdict[int, int] = defaultdict(int)
        for citation in evidence:
            counts[citation.entry_date] += 1
        return tuple(
            RouteWaypoint(
                waypoint_id=str(_field(row, columns, "waypoint_id")),
                entry_date=int(_field(row, columns, "entry_date")),
                name=str(_field(row, columns, "name")),
                lat=float(_field(row, columns, "lat")),
                lon=float(_field(row, columns, "lon")),
                citation_passage_ids=tuple(
                    _field(row, columns, "citation_passage_ids")
                ),
                source_note=str(_field(row, columns, "source_note")),
                evidence_count=counts[int(_field(row, columns, "entry_date"))],
            )
            for row in rows
        )

    async def _with_agreement_all(
        self, requirements: Sequence[AssetRequirement], plan: ResearchPlan
    ) -> tuple[AssetRequirement, ...]:
        return tuple(
            await asyncio.gather(
                *(
                    self._with_agreement(requirement, plan)
                    for requirement in requirements
                )
            )
        )

    async def _with_agreement(
        self, requirement: AssetRequirement, plan: ResearchPlan
    ) -> AssetRequirement:
        expansions = _category_terms().get(requirement.category, ())
        terms = tuple(dict.fromkeys(
            token
            for term in (*requirement.search_terms, *expansions)
            for token in re.findall(r"[a-z0-9]+", term.casefold())
            if len(token) >= 3
        ))
        escaped = (term.replace("'", "''") for term in terms)
        array_literal = "[" + ",".join(f"'{term}'" for term in escaped) + "]"
        query = f"""
SELECT author_id, author_display_name, entry_date, mention_count,
       observation_count, passage_ids
FROM sourcecut.author_date_matrix(
    terms={array_literal}, start={plan.window_start}, end={plan.window_end}
)
LIMIT 500
""".strip()
        columns, rows = await self._run_query(query, "agreement")
        if not rows:
            return requirement
        authors = {
            str(_field(row, columns, "author_id")): str(
                _field(row, columns, "author_display_name")
            )
            for row in rows
        }
        indexed = {
            (
                str(_field(row, columns, "author_id")),
                int(_field(row, columns, "entry_date")),
            ): row
            for row in rows
        }
        cells: list[AgreementCell] = []
        for author_id, author_name in authors.items():
            for entry_date in window_dates(plan.window_start, plan.window_end):
                row = indexed.get((author_id, entry_date))
                if row is None:
                    cells.append(
                        AgreementCell(
                            author_id=author_id,
                            author_display_name=author_name,
                            entry_date=entry_date,
                            state="no_entry",
                        )
                    )
                    continue
                mentions = int(_field(row, columns, "mention_count"))
                observations = int(_field(row, columns, "observation_count"))
                cells.append(
                    AgreementCell(
                        author_id=author_id,
                        author_display_name=author_name,
                        entry_date=entry_date,
                        state=(
                            "mentions"
                            if mentions or observations
                            else "entry_without_mention"
                        ),
                        mention_count=mentions,
                        observation_count=observations,
                        passage_ids=tuple(_field(row, columns, "passage_ids")),
                    )
                )
        supporting = [cell for cell in cells if cell.state == "mentions"]
        return requirement.model_copy(
            update={
                "agreement": tuple(cells),
                "corroboration_authors": len({cell.author_id for cell in supporting}),
                "corroboration_days": len({cell.entry_date for cell in supporting}),
            }
        )

    async def _rank_assets(
        self,
        requirement: AssetRequirement,
        token_assets: Sequence[MediaAsset],
    ) -> list[MediaAsset]:
        token_ranked = sorted(
            token_assets,
            key=lambda asset: (_match_score(asset, requirement), asset.asset_id),
            reverse=True,
        )
        if self._embedder is None:
            return token_ranked
        requirement_text = "\n".join(
            (requirement.title, requirement.production_need, *requirement.search_terms)
        )
        vector = self._query_vectors.get(requirement_text)
        if vector is None:
            vector = await asyncio.to_thread(self._embedder.embed_query, requirement_text)
            self._query_vectors[requirement_text] = vector
        columns, rows = await self._run_query(
            _semantic_media_query(vector), "semantic_media"
        )
        semantic_ranked = [_media_asset(row, columns) for row in rows]
        return list(
            {
                asset.asset_id: asset
                for asset in (*semantic_ranked, *token_ranked)
            }.values()
        )

    async def _run_query(self, query: str, stage: str) -> tuple[list[str], list[Any]]:
        started = time.perf_counter()
        try:
            payload = await self._mcp.call_tool("run_query", {"query": query})
            columns, rows = _query_rows(payload)
        except Exception:
            self._emit(
                "mcp_tool_call",
                stage,
                "failed",
                "ClickHouse MCP query failed.",
                {
                    "tool": "run_query",
                    "access_path": "mcp_runtime",
                    "sql": sanitize_sql(query),
                    "row_count": 0,
                },
                int((time.perf_counter() - started) * 1000),
            )
            raise
        self._emit(
            "mcp_tool_call",
            stage,
            "complete",
            f"ClickHouse MCP returned {len(rows)} row(s).",
            {
                "tool": "run_query",
                "access_path": "mcp_runtime",
                "sql": sanitize_sql(query),
                "row_count": len(rows),
            },
            int((time.perf_counter() - started) * 1000),
        )
        return columns, rows

    def _emit(
        self,
        event_type: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any],
        duration_ms: int = 0,
    ) -> None:
        if self.event_sink is not None:
            self.event_sink(
                event_type,
                stage,
                status,
                message,
                payload,
                duration_ms,
            )


def build_asset_requirements(
    evidence: Sequence[EvidenceCitation],
    plan: ResearchPlan | None = None,
) -> tuple[AssetRequirement, ...]:
    """Attach retrieved evidence to the planned requirements.

    Requirements come from the plan; evidence decides which of them survive.
    A requirement with no citations is dropped from the board but still
    appears in the coverage report as unmet.
    """
    resolved = plan.requirements if plan is not None else BASELINE_REQUIREMENTS
    scope = plan.scope_id if plan is not None else "bitterroot-september-1805"
    grouped: defaultdict[str, list[EvidenceCitation]] = defaultdict(list)
    for citation in evidence:
        grouped[citation.category].append(citation)

    requirements: list[AssetRequirement] = []
    for planned in resolved:
        citations = tuple(grouped.get(planned.category, ()))
        if not citations:
            continue
        observed_terms = tuple(sorted({item.canonical_term.casefold() for item in citations}))
        requirements.append(
            AssetRequirement(
                requirement_id=f"{scope}:{planned.category}",
                title=planned.title,
                category=planned.category,
                production_need=planned.production_need,
                search_terms=tuple(
                    dict.fromkeys((*planned.search_terms, *observed_terms))
                ),
                evidence=citations[:12],
            )
        )
    return tuple(requirements)


def evaluate_coverage(
    requirements: Sequence[AssetRequirement], plan: ResearchPlan
) -> CoverageReport:
    """Score each planned requirement against its own success criterion.

    This is the goal-monitoring step: it is what tells the research loop
    whether another round is worth running, and it is reported on the board so
    a reader can see what the corpus did not support.
    """
    found = {requirement.category: requirement for requirement in requirements}
    entries: list[CoverageEntry] = []
    for planned in plan.requirements:
        requirement = found.get(planned.category)
        citations = requirement.evidence if requirement is not None else ()
        authors = {citation.author_display_name for citation in citations}
        if not citations:
            status: str = "unmet"
        elif len(authors) >= planned.minimum_authors:
            status = "met"
        else:
            status = "single_source"
        entries.append(
            CoverageEntry(
                requirement_id=(
                    requirement.requirement_id
                    if requirement is not None
                    else f"{plan.scope_id}:{planned.category}"
                ),
                category=planned.category,
                status=status,  # type: ignore[arg-type]
                evidence_count=len(citations),
                author_count=len(authors),
                minimum_authors=planned.minimum_authors,
                success_criteria=planned.success_criteria,
            )
        )
    return CoverageReport(entries=tuple(entries))


def _unique_citations(
    citations: Sequence[EvidenceCitation],
) -> tuple[EvidenceCitation, ...]:
    unique: dict[str, EvidenceCitation] = {}
    for citation in citations:
        unique.setdefault(citation.observation_id, citation)
    return tuple(unique.values())


def _derive_passage_evidence(
    rows: Sequence[Any],
    columns: list[str],
    categories: Mapping[str, Sequence[str]] | None = None,
) -> tuple[EvidenceCitation, ...]:
    """Keyword-anchored citations derived from raw passage text.

    Used by the observation fallback and by the coverage loop's gap rounds.
    ``categories`` narrows the scan to one requirement's vocabulary; the
    default scans the full curated term set.
    """
    vocabulary = categories if categories is not None else _category_terms()
    citations: list[EvidenceCitation] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        passage_id = str(_field(row, columns, "passage_id"))
        passage_text = str(_field(row, columns, "passage_text"))
        lowered = passage_text.casefold()
        for category, terms in vocabulary.items():
            match = next(
                (
                    (term, lowered.find(term.casefold()))
                    for term in terms
                    if lowered.find(term.casefold()) >= 0
                ),
                None,
            )
            if match is None or (passage_id, category) in seen:
                continue
            term, start = match
            quote_start = max(0, start - 100)
            quote_end = min(len(passage_text), start + len(term) + 100)
            quote = passage_text[quote_start:quote_end].strip()
            digest = hashlib.sha256(
                f"{passage_id}\0{category}\0{start}".encode()
            ).hexdigest()[:24]
            citations.append(
                EvidenceCitation(
                    observation_id=f"passage-term:{digest}",
                    passage_id=passage_id,
                    author_display_name=str(
                        _field(row, columns, "author_display_name")
                    ),
                    entry_date=int(_field(row, columns, "entry_date")),
                    category=category,
                    canonical_term=term,
                    source_quote=quote,
                    confidence=1.0,
                )
            )
            seen.add((passage_id, category))
    return tuple(citations)


_REPO_ROOT = Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def _category_terms() -> dict[str, tuple[str, ...]]:
    override = os.getenv("SOURCECUT_DATA_DIR")
    data_dir = Path(override) if override else _REPO_ROOT / "data"
    terms_path = data_dir / "reference" / "term_expansions.json"
    if not terms_path.is_file():
        raise RuntimeError(
            f"Term expansion reference data missing at {terms_path}. "
            "Ship the data/ directory with the application or set SOURCECUT_DATA_DIR."
        )
    records = json.loads(terms_path.read_text(encoding="utf-8"))
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for record in records:
        grouped[str(record["category"])].extend(str(value) for value in record["expansions"])
    return {category: tuple(dict.fromkeys(terms)) for category, terms in grouped.items()}


def verify_asset(
    asset: MediaAsset,
    requirement: AssetRequirement,
    *,
    visual_inspection: VisualInspection | None = None,
) -> VerifiedAsset:
    if asset.rights_status not in REUSABLE_RIGHTS:
        confidence = BoardConfidence.RIGHTS_REJECTED
        reason = "Rejected because item-level rights are not explicitly reusable."
    elif _match_score(asset, requirement) == 0:
        confidence = BoardConfidence.UNSUPPORTED
        reason = "Archive metadata does not match this evidence-derived requirement."
    elif visual_inspection is not None and not visual_inspection.relevant:
        confidence = BoardConfidence.UNSUPPORTED
        reason = "Gemini visual inspection found no visible support for this requirement."
    elif asset.historical_relationship in {
        HistoricalRelationship.PRIMARY,
        HistoricalRelationship.NEAR_CONTEMPORARY,
    }:
        author_count = len({item.author_display_name for item in requirement.evidence})
        confidence = (
            BoardConfidence.HIGH if author_count >= 2 else BoardConfidence.SINGLE_SOURCE
        )
        reason = "Reusable archive metadata matches the requirement and is near-contemporary."
    else:
        confidence = BoardConfidence.INTERPRETIVE
        reason = (
            "Useful visual or contextual reference, but not direct expedition evidence; "
            f"relationship is {asset.historical_relationship}."
        )
    return VerifiedAsset(
        asset=BoardMediaAsset.from_media_asset(asset),
        requirement_id=requirement.requirement_id,
        confidence=confidence,
        production_use=requirement.production_need,
        why_selected=reason,
        evidence=requirement.evidence,
        historical_relationship=asset.historical_relationship,
        visual_inspection=visual_inspection,
    )


def memory_enabled() -> bool:
    raw = os.getenv("SOURCECUT_VOCABULARY_MEMORY", "true").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"SOURCECUT_VOCABULARY_MEMORY has unsupported value {raw!r}")


def create_board_service(*, event_sink: EventSink | None = None) -> ResearchBoardService:
    """The one place the full research service is wired.

    The API and `sourcecut-capture-example` must build the same thing: a
    snapshot captured from a thinner service understates the pipeline it is
    presented as a record of. The first captured board came out of a bare
    service and reported `planner: static` with no visual inspection, while the
    deployed API was running the Gemini planner on the same prompt.
    """
    from pipelines.embeddings import EmbeddingSettings, create_embedder
    from sourcecut_api.db.client import get_clickhouse_client
    from sourcecut_api.repositories import TermExpansionRepository

    genai_settings = GenaiSettings.from_env()
    embedding_settings = EmbeddingSettings.from_env()
    memory: TermExpansionRepository | None = None
    if memory_enabled():
        try:
            memory = TermExpansionRepository(get_clickhouse_client())
        except Exception:
            memory = None
    return ResearchBoardService(
        ClickHouseMcpClient(ClickHouseMcpSettings.from_env()),
        visual_inspector=(
            create_visual_inspector() if genai_settings.configured else None
        ),
        embedder=create_embedder(embedding_settings) if embedding_settings.enabled else None,
        planner=create_planner(),
        max_research_rounds=int(os.getenv("SOURCECUT_RESEARCH_ROUNDS", "2")),
        memory=memory,
        event_sink=event_sink,
    )


def create_visual_inspector(*, api_key: str | None = None) -> GeminiVisualInspector:
    client = create_genai_client(api_key=api_key)
    return GeminiVisualInspector(
        client,
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
    )


def _vector_literal(vector: Sequence[float]) -> str:
    if not vector or any(not math.isfinite(value) for value in vector):
        raise ValueError("Embedding vectors must contain finite values")
    return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"


def _semantic_passage_query(
    vector: Sequence[float],
    start: int = BITTERROOT_START,
    end: int = BITTERROOT_END,
) -> str:
    return f"""
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN {int(start)} AND {int(end)}
  AND notEmpty(embedding)
ORDER BY cosineDistance(embedding, {_vector_literal(vector)}) ASC
LIMIT 40
""".strip()


def _semantic_media_query(vector: Sequence[float]) -> str:
    return f"""
SELECT
    asset_id, provider, provider_id, title, description, creators, asset_type,
    creation_date_text, creation_year, subjects, places, source_url, media_url,
    thumbnail_path, rights_status, rights_text, historical_relationship,
    raw_metadata, metadata_sha256
FROM sourcecut.media_assets FINAL
WHERE notEmpty(embedding)
ORDER BY cosineDistance(embedding, {_vector_literal(vector)}) ASC
LIMIT 40
""".strip()


def _match_score(asset: MediaAsset, requirement: AssetRequirement) -> int:
    haystack = " ".join(
        (
            asset.title,
            asset.description,
            *asset.subjects,
            *asset.places,
            *asset.creators,
        )
    ).casefold()
    terms = {
        token
        for term in requirement.search_terms
        for token in re.findall(r"[a-z0-9]+", term.casefold())
        if len(token) >= 3 and token not in STOP_WORDS
    }
    return sum(1 for term in terms if term in haystack)


def _warnings(
    reviewed: Sequence[VerifiedAsset],
    requirements: Sequence[AssetRequirement],
    assets: Sequence[MediaAsset],
    inspection_failures: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    unsupported = sum(item.confidence is BoardConfidence.UNSUPPORTED for item in reviewed)
    interpretive = sum(item.confidence is BoardConfidence.INTERPRETIVE for item in reviewed)
    rejected = sum(asset.rights_status not in REUSABLE_RIGHTS for asset in assets)
    if unsupported:
        warnings.append(f"{unsupported} candidate matches were unsupported and not selected.")
    if interpretive:
        warnings.append(
            f"{interpretive} reviewed candidates are interpretive references, not expedition proof."
        )
    if rejected:
        warnings.append(f"{rejected} assets were excluded by item-level rights filtering.")
    if inspection_failures:
        warnings.append(
            f"{inspection_failures} optional visual inspections failed; candidates stayed "
            "at metadata-derived confidence."
        )
    if not requirements:
        warnings.append("No validated evidence was available; no asset requirement was inferred.")
    return tuple(warnings)


def _query_rows(payload: Any) -> tuple[list[str], list[Any]]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("ClickHouse MCP returned an unexpected query payload")
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise RuntimeError("ClickHouse MCP query omitted columns or rows")
    return [str(column) for column in columns], rows


def _field(row: Any, columns: list[str], name: str) -> Any:
    if isinstance(row, Mapping):
        return row[name]
    return row[columns.index(name)]


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return ()


def _media_asset(row: Any, columns: list[str]) -> MediaAsset:
    return MediaAsset(
        asset_id=str(_field(row, columns, "asset_id")),
        provider=str(_field(row, columns, "provider")),
        provider_id=str(_field(row, columns, "provider_id")),
        title=str(_field(row, columns, "title")),
        description=str(_field(row, columns, "description")),
        creators=_string_tuple(_field(row, columns, "creators")),
        asset_type=str(_field(row, columns, "asset_type")),
        creation_date_text=str(_field(row, columns, "creation_date_text")),
        creation_year=int(_field(row, columns, "creation_year")),
        subjects=_string_tuple(_field(row, columns, "subjects")),
        places=_string_tuple(_field(row, columns, "places")),
        source_url=str(_field(row, columns, "source_url")),
        media_url=str(_field(row, columns, "media_url")),
        thumbnail_path=str(_field(row, columns, "thumbnail_path")),
        rights_status=str(_field(row, columns, "rights_status")),
        rights_text=str(_field(row, columns, "rights_text")),
        historical_relationship=str(_field(row, columns, "historical_relationship")),
        raw_metadata=str(_field(row, columns, "raw_metadata")),
        metadata_sha256=_hash_text(_field(row, columns, "metadata_sha256")),
    )


def _hash_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii")
    text = str(value)
    match = re.fullmatch(r"b(['\"])([0-9a-f]{64})\1", text)
    return match.group(2) if match else text


async def _build_live_board(prompt: str, *, inspect_visuals: bool) -> ResearchBoard:
    client = ClickHouseMcpClient(ClickHouseMcpSettings.from_env())
    inspector = create_visual_inspector() if inspect_visuals else None
    return await ResearchBoardService(client, visual_inspector=inspector).build_board(prompt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the SourceCut Bitterroot research board")
    parser.add_argument("prompt")
    parser.add_argument("--skip-visual-inspection", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    board = asyncio.run(
        _build_live_board(args.prompt, inspect_visuals=not args.skip_visual_inspection)
    )
    if args.summary:
        counts = Counter(item.confidence for item in board.reviewed_assets)
        first_citation = (
            board.evidence_matrix[0].evidence[0].model_dump(mode="json")
            if board.evidence_matrix
            else None
        )
        print(
            json.dumps(
                {
                    "title": board.title,
                    "requirement_count": len(board.evidence_matrix),
                    "section_count": len(board.sections),
                    "selected_assets": sum(len(section.assets) for section in board.sections),
                    "confidence_counts": counts,
                    "visual_inspections": sum(
                        item.visual_inspection is not None for item in board.reviewed_assets
                    ),
                    "warnings": board.warnings,
                    "sources_used": board.sources_used,
                    "first_citation": first_citation,
                },
                indent=2,
            )
        )
    else:
        print(board.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
