# Task 027 — Agentic Research Workflows

## Goal

Make the product path agentic. Until now the ADK agent — with its tool loop, SQL guardrail, and
per-call telemetry — ran only behind the `sourcecut-research` CLI. The web flow executed
hardcoded SQL and ignored the filmmaker's brief apart from embedding it, so the demo showed
ClickHouse MCP but never showed an agent.

## Read first
- `AGENTS.md`
- `docs/hackathon-build/decisions.md` (ADR-019 through ADR-022)
- `apps/api/sourcecut_api/agents/research.py`
- `apps/api/sourcecut_api/services/board.py`

## Scope

### Planning (ADR-019)

- `agents/planner.py`: `ResearchPlan` / `PlannedRequirement` typed models, a `ResearchPlanner`
  protocol, `GeminiResearchPlanner`, and `StaticResearchPlanner`.
- The planner selects a `scope_id` from `data/reference/research_scopes.json`; the window is read
  from that file, never from model output.
- `build_plan` validates before use: known scope, allowed categories, deduplicated categories,
  bounded requirement and term counts, restricted term charset.
- Deterministic keyword routing backs the model planner and takes over on validation failure or
  model error, so the board path runs with no credential configured.
- Board queries, agreement matrices, route waypoints, and semantic retrieval take their window
  from the plan.

### Coverage rounds (ADR-020)

- `evaluate_coverage` scores every planned requirement against its own success criterion.
- Unmet requirements trigger at most one extra round (`SOURCECUT_RESEARCH_ROUNDS`, default 2),
  widening only their vocabulary inside the same window.
- Coverage is reported on the board, including requirements the corpus did not support.
- Timeline events: `plan_created`, `coverage_evaluated`, `gap_replan`, `memory_updated`.

### Vocabulary memory (ADR-021)

- `repositories/terms.py` writes productive gap terms back to `term_expansions` with
  `provenance='discovered'` (migration `131`).
- Curated rows keep their provenance and only gain terms. Memory failures never fail a board.

### Self-consistency extraction

- `pipelines/extraction/consistency.py` samples one passage N times in parallel and keeps only
  candidates seen at least `threshold` times, matched on the exact span claimed.
- Consensus results carry their own prompt version and idempotency key.
- `sourcecut-eval run --candidates LABEL=PATH` scores variants against the same reviewed fixture.

### Specialist pipeline (ADR-022)

- `build_research_pipeline` composes planner, researcher, and auditor as an ADK `SequentialAgent`,
  separated by tool access. Opt in with `sourcecut-research --pipeline`.

## Do not
- let a plan, coverage entry, embedding, or discovered term become evidence;
- allow the model to set a date window directly;
- widen the window, lower a success criterion, or loop unbounded in a gap round;
- give the planner or auditor stage any tools;
- make the default test suite require a credential or network.

## Acceptance criteria

1. A board build with no Gemini credential still produces a plan, coverage report, and board.
2. A brief naming a different expedition segment routes to that scope's window.
3. A requirement the first pass cannot satisfy triggers exactly one widened round; when the
   widened search finds passages, coverage flips to met and the term is recorded as discovered.
4. When widening finds nothing, the loop stops and the board reports the requirement unmet.
5. Reviewing a corrected clip reports which flagged details the correction resolved.
6. Consensus extraction discards candidates below the vote threshold and is scored against the
   reviewed fixture alongside single-shot output.
7. The pipeline runtime exposes tools only on its research stage.
