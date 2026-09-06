"""Research planning and scope routing.

Plan-then-execute: a planner turns the filmmaker's brief into a typed
:class:`ResearchPlan` (which corpus window, which production requirements,
which search vocabulary), and deterministic application code executes it.

The model never chooses a date window directly — it selects one of the
curated scopes in ``data/reference/research_scopes.json`` and the window is
read from that file, so a plan cannot widen the corpus slice or invent a
period. Plans carry no historical claims; evidence still comes only from
stored, validated passages (ADR-004/ADR-013).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import defaultdict
from collections.abc import Sequence
from functools import lru_cache
from typing import Annotated, Any, Protocol

from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from sourcecut_api.constants import reference_data_path
from sourcecut_api.models.observation import ObservationCategory
from sourcecut_api.models.plan import (
    CoverageEntry,
    PlannedRequirement,
    ResearchPlan,
    ResearchScope,
)
from sourcecut_api.telemetry import add_counter, telemetry_span

DEFAULT_PLANNER_MODEL = "gemini-2.5-flash"
PROMPT_VERSION = "research-plan-v1"
MAX_REQUIREMENTS = 8
MAX_TERMS_PER_REQUIREMENT = 12
MAX_GAP_TERMS = 8
TERM_PATTERN = re.compile(r"^[a-z0-9][a-z0-9 '\-]{1,39}$")

BASELINE_REQUIREMENTS: tuple[PlannedRequirement, ...] = (
    PlannedRequirement(
        category="weather",
        title="Weather and exposure",
        production_need=(
            "Visual references for cold, precipitation, and exposed mountain travel."
        ),
        search_terms=("snow", "cold", "rain", "mountain", "bitterroot", "rocky"),
        success_criteria="Two authors describe weather or exposure inside the window.",
    ),
    PlannedRequirement(
        category="terrain",
        title="Route geography and terrain",
        production_need=(
            "Maps and landscape references for steep, forested route geography."
        ),
        search_terms=("mountain", "trail", "rock", "timber", "bitterroot", "rocky", "map"),
        success_criteria="Two authors describe terrain or route geography.",
    ),
    PlannedRequirement(
        category="transportation",
        title="Expedition transportation",
        production_need=(
            "References for horse travel and constrained movement on mountain trails."
        ),
        search_terms=("horse", "trail", "expedition", "lewis", "clark", "bitterroot"),
        success_criteria="Two authors describe horses or movement.",
    ),
    PlannedRequirement(
        category="food",
        title="Food scarcity",
        production_need="Documentary references for expedition provisions and food scarcity.",
        search_terms=("food", "hunger", "provision", "expedition", "lewis", "clark"),
        success_criteria="Two authors describe provisions or hunger.",
    ),
    PlannedRequirement(
        category="shelter",
        title="Camp and shelter",
        production_need="References for temporary camps and shelter in mountain conditions.",
        search_terms=("camp", "shelter", "mountain", "expedition", "lewis", "clark"),
        success_criteria="Two authors describe camps or shelter.",
    ),
    PlannedRequirement(
        category="equipment",
        title="Clothing and equipment",
        production_need="Documentary references for expedition clothing and field equipment.",
        search_terms=("equipment", "clothing", "expedition", "lewis", "clark"),
        success_criteria="Two authors describe clothing or equipment.",
    ),
)

PLANNER_INSTRUCTION = """
You plan historical research for a film production, over a fixed primary-source corpus of
Lewis and Clark expedition journals.

You do NOT answer historical questions and you do NOT state historical facts. You only decide
what to investigate. Evidence is retrieved afterwards by deterministic application code from
stored, validated journal passages.

Given the filmmaker's brief:
1. Choose exactly one scope_id from the supplied scopes. Pick the scope whose period and
   subject best match the brief. If nothing matches well, choose the default scope.
2. Produce between two and six production requirements. Each requirement names one evidence
   category, the production need it serves, the period search vocabulary to look for, and a
   success criterion.
3. Search terms must be words a journal keeper in 1805 would actually have written. Prefer
   period vocabulary ("provisions", "mockersons") over modern paraphrase ("supply chain",
   "footwear"). Include singular forms; the retrieval layer expands them.
4. Do not invent place names, people, or events. Do not assert what the journals contain.

Allowed categories: weather, terrain, transportation, food, shelter, equipment, person, animal,
place, health, event.
""".strip()

GAP_INSTRUCTION = """
A first research pass failed to find sufficient evidence for some production requirements.

For each unmet requirement, propose additional period search vocabulary that a journal keeper
in 1805 might have used for the same idea, including plausible historical spellings and
inflected forms. Do not assert that the corpus contains these words; you are widening a search,
not making a claim. Return only categories that were listed as unmet.
""".strip()


class PlannedRequirementDraft(BaseModel):
    """Planner output for one requirement, before validation."""

    model_config = ConfigDict(extra="forbid")

    category: ObservationCategory
    title: Annotated[str, Field(min_length=2, max_length=120)]
    production_need: Annotated[str, Field(min_length=2, max_length=400)]
    search_terms: list[str]
    success_criteria: Annotated[str, Field(min_length=2, max_length=300)]
    minimum_authors: int = 2


class ResearchPlanDraft(BaseModel):
    """Planner output. The window is resolved from the chosen scope, not the model."""

    model_config = ConfigDict(extra="forbid")

    scope_id: str
    rationale: Annotated[str, Field(min_length=2, max_length=600)]
    requirements: list[PlannedRequirementDraft]


class GapTermsDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ObservationCategory
    additional_terms: list[str]


class GapExpansionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[GapTermsDraft]


class PlanValidationError(ValueError):
    pass


class ResearchPlanner(Protocol):
    name: str

    async def plan(self, prompt: str) -> ResearchPlan: ...

    async def expand_gaps(
        self, prompt: str, plan: ResearchPlan, gaps: Sequence[CoverageEntry]
    ) -> dict[str, tuple[str, ...]]: ...


@lru_cache(maxsize=1)
def load_scopes() -> tuple[ResearchScope, ...]:
    path = reference_data_path("research_scopes.json")
    if not path.is_file():
        raise RuntimeError(
            f"Research scope reference data missing at {path}. "
            "Ship the data/ directory with the application or set SOURCECUT_DATA_DIR."
        )
    records = json.loads(path.read_text(encoding="utf-8"))
    scopes = tuple(ResearchScope.model_validate(record) for record in records)
    if not scopes:
        raise RuntimeError("Research scope reference data is empty")
    return scopes


def default_scope(scopes: Sequence[ResearchScope] | None = None) -> ResearchScope:
    resolved = tuple(scopes or load_scopes())
    for scope in resolved:
        if scope.default:
            return scope
    return resolved[0]


def route_scope(
    prompt: str, scopes: Sequence[ResearchScope] | None = None
) -> ResearchScope:
    """Deterministic keyword routing used as the fallback and as a safety net.

    Longer keyword phrases score higher than single words so that
    "september 1805" outweighs an incidental "mountains".
    """
    resolved = tuple(scopes or load_scopes())
    lowered = prompt.casefold()
    best = default_scope(resolved)
    best_score = 0
    for scope in resolved:
        score = sum(
            len(keyword.split())
            for keyword in scope.keywords
            if keyword.casefold() in lowered
        )
        if score > best_score:
            best, best_score = scope, score
    return best


def normalize_terms(terms: Sequence[str], limit: int) -> tuple[str, ...]:
    """Lowercase, de-duplicate, and drop anything outside the safe term charset."""
    seen: dict[str, None] = {}
    for term in terms:
        candidate = " ".join(str(term).casefold().split())
        if TERM_PATTERN.fullmatch(candidate):
            seen.setdefault(candidate, None)
    return tuple(seen)[:limit]


def build_plan(
    draft: ResearchPlanDraft,
    *,
    planner: str,
    scopes: Sequence[ResearchScope] | None = None,
) -> ResearchPlan:
    """Assemble a validated plan, resolving the window from the chosen scope."""
    resolved = tuple(scopes or load_scopes())
    scope = next((item for item in resolved if item.scope_id == draft.scope_id), None)
    if scope is None:
        raise PlanValidationError(
            f"Unknown scope_id {draft.scope_id!r}; choose one of "
            f"{', '.join(item.scope_id for item in resolved)}"
        )
    if not draft.requirements:
        raise PlanValidationError("A plan needs at least one requirement")

    requirements: list[PlannedRequirement] = []
    used: set[str] = set()
    for item in draft.requirements[:MAX_REQUIREMENTS]:
        if item.category in used:
            continue
        terms = normalize_terms(item.search_terms, MAX_TERMS_PER_REQUIREMENT)
        if not terms:
            raise PlanValidationError(
                f"Requirement {item.category!r} has no usable search terms"
            )
        used.add(item.category)
        requirements.append(
            PlannedRequirement(
                category=item.category,
                title=item.title.strip(),
                production_need=item.production_need.strip(),
                search_terms=terms,
                success_criteria=item.success_criteria.strip(),
                minimum_authors=max(1, min(3, item.minimum_authors)),
            )
        )
    if not requirements:
        raise PlanValidationError("A plan needs at least one usable requirement")

    return ResearchPlan(
        scope_id=scope.scope_id,
        title=scope.title,
        window_start=scope.window_start,
        window_end=scope.window_end,
        rationale=draft.rationale.strip(),
        requirements=tuple(requirements),
        planner=planner,
        prompt_version=PROMPT_VERSION,
    )


class StaticResearchPlanner:
    """Deterministic planner: keyword routing plus the baseline requirement set.

    Used when no Gemini credential is configured, and as the fallback when a
    model plan fails validation. Keeps the whole board path runnable offline.
    """

    name = "static"

    def __init__(self, scopes: Sequence[ResearchScope] | None = None) -> None:
        self._scopes = tuple(scopes) if scopes is not None else None

    async def plan(self, prompt: str) -> ResearchPlan:
        scopes = self._scopes or load_scopes()
        scope = route_scope(prompt, scopes)
        return ResearchPlan(
            scope_id=scope.scope_id,
            title=scope.title,
            window_start=scope.window_start,
            window_end=scope.window_end,
            rationale=(
                "Keyword routing selected this corpus segment; the baseline production "
                "requirement set was applied."
            ),
            requirements=BASELINE_REQUIREMENTS,
            planner=self.name,
            prompt_version=PROMPT_VERSION,
        )

    async def expand_gaps(
        self, prompt: str, plan: ResearchPlan, gaps: Sequence[CoverageEntry]
    ) -> dict[str, tuple[str, ...]]:
        del prompt
        existing = {
            requirement.category: set(requirement.search_terms)
            for requirement in plan.requirements
        }
        expansions = _curated_expansions()
        widened: dict[str, tuple[str, ...]] = {}
        for gap in gaps:
            extra = tuple(
                term
                for term in expansions.get(gap.category, ())
                if term not in existing.get(gap.category, set())
            )
            if extra:
                widened[gap.category] = extra[:MAX_GAP_TERMS]
        return widened


class GeminiResearchPlanner:
    """Model planner with deterministic validation and a static fallback."""

    name = "gemini"

    def __init__(
        self,
        client: Any,
        *,
        model: str = DEFAULT_PLANNER_MODEL,
        scopes: Sequence[ResearchScope] | None = None,
        fallback: ResearchPlanner | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._scopes = tuple(scopes) if scopes is not None else None
        self._fallback = fallback or StaticResearchPlanner(scopes)

    @property
    def model(self) -> str:
        return self._model

    async def plan(self, prompt: str) -> ResearchPlan:
        scopes = self._scopes or load_scopes()
        contents = _plan_prompt(prompt, scopes)
        with telemetry_span(
            "sourcecut.research.plan",
            {"gen_ai.request.model": self._model, "sourcecut.planner": self.name},
        ):
            try:
                draft = await self._generate(contents, ResearchPlanDraft)
                plan = build_plan(draft, planner=f"{self.name}:{self._model}", scopes=scopes)
            except Exception as error:
                add_counter(
                    "sourcecut.research.plans", 1, {"planner": self.name, "status": "fallback"}
                )
                plan = await self._fallback.plan(prompt)
                return plan.model_copy(
                    update={
                        "rationale": (
                            f"Model planning failed ({type(error).__name__}); "
                            f"{plan.rationale}"
                        )
                    }
                )
        add_counter("sourcecut.research.plans", 1, {"planner": self.name, "status": "ok"})
        return plan

    async def expand_gaps(
        self, prompt: str, plan: ResearchPlan, gaps: Sequence[CoverageEntry]
    ) -> dict[str, tuple[str, ...]]:
        if not gaps:
            return {}
        contents = _gap_prompt(prompt, plan, gaps)
        gap_categories = {gap.category for gap in gaps}
        existing = {
            requirement.category: set(requirement.search_terms)
            for requirement in plan.requirements
        }
        try:
            with telemetry_span(
                "sourcecut.research.gap_expansion",
                {"gen_ai.request.model": self._model, "sourcecut.gap.count": len(gaps)},
            ):
                draft = await self._generate(contents, GapExpansionDraft)
        except Exception:
            return await self._fallback.expand_gaps(prompt, plan, gaps)

        widened: dict[str, tuple[str, ...]] = {}
        for item in draft.categories:
            if item.category not in gap_categories:
                continue
            terms = tuple(
                term
                for term in normalize_terms(item.additional_terms, MAX_GAP_TERMS)
                if term not in existing.get(item.category, set())
            )
            if terms:
                widened[item.category] = terms
        if not widened:
            return await self._fallback.expand_gaps(prompt, plan, gaps)
        return widened

    async def _generate(self, contents: str, schema: type[BaseModel]) -> Any:
        instruction = (
            PLANNER_INSTRUCTION if schema is ResearchPlanDraft else GAP_INSTRUCTION
        )

        def generate() -> Any:
            return self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    temperature=0,
                    response_mime_type="application/json",
                    response_json_schema=schema.model_json_schema(),
                ),
            )

        response = await asyncio.to_thread(generate)
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        if parsed is not None:
            return schema.model_validate(parsed)
        text = getattr(response, "text", None)
        if text is None:
            raise ValueError("Gemini returned no planning output")
        return schema.model_validate_json(text)


def create_planner(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> ResearchPlanner:
    """Build the configured planner, or the deterministic one without a credential."""
    if not api_key:
        return StaticResearchPlanner()
    from google import genai

    # vertexai=False is explicit: an inherited GOOGLE_GENAI_USE_VERTEXAI makes
    # the client ignore the key, fail on Vertex auth, and degrade the planner to
    # static without saying so. Pin it whatever the environment carries.
    return GeminiResearchPlanner(
        genai.Client(api_key=api_key, vertexai=False),
        model=model or os.getenv("GEMINI_MODEL", DEFAULT_PLANNER_MODEL),
    )


def _plan_prompt(prompt: str, scopes: Sequence[ResearchScope]) -> str:
    catalog = "\n".join(
        f"- {scope.scope_id}: {scope.title} "
        f"({scope.window_start}-{scope.window_end})"
        f"{' [default]' if scope.default else ''}"
        for scope in scopes
    )
    return (
        f"Filmmaker brief:\n{prompt.strip()}\n\n"
        f"Available corpus scopes:\n{catalog}\n\n"
        "Return the research plan."
    )


def _gap_prompt(
    prompt: str, plan: ResearchPlan, gaps: Sequence[CoverageEntry]
) -> str:
    current = {
        requirement.category: requirement.search_terms
        for requirement in plan.requirements
    }
    lines = "\n".join(
        f"- {gap.category}: {gap.status}, {gap.evidence_count} citation(s) from "
        f"{gap.author_count} author(s); already searched: "
        f"{', '.join(current.get(gap.category, ()))}"
        for gap in gaps
    )
    return (
        f"Filmmaker brief:\n{prompt.strip()}\n\n"
        f"Corpus window: {plan.window_start} to {plan.window_end} ({plan.title})\n\n"
        f"Unmet requirements:\n{lines}\n\n"
        "Return additional search vocabulary for these categories only."
    )


@lru_cache(maxsize=1)
def _curated_expansions() -> dict[str, tuple[str, ...]]:
    """Curated vocabulary grouped by category, used to widen a failed search."""
    path = reference_data_path("term_expansions.json")
    if not path.is_file():
        return {}
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for record in json.loads(path.read_text(encoding="utf-8")):
        grouped[str(record["category"])].extend(
            str(value) for value in record.get("expansions", ())
        )
    return {
        category: normalize_terms(terms, MAX_TERMS_PER_REQUIREMENT)
        for category, terms in grouped.items()
    }
