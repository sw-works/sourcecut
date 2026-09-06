# Diagrams

Diagrams as source. Each `src/*.mjs` places its nodes on explicit coordinates and renders
through a small dependency-free SVG builder, so a picture changes only when someone changes
it, and the change is readable in the diff.

## The agentic patterns

One diagram per pattern, each drawn on the one SourceCut workflow that embodies it. Eight
boxes or fewer, one line per box; what was cut is named in the footnote. These are the
slide and video set.

| # | Pattern | Workflow shown | Source |
|---|---|---|---|
| P1 | [planning](p1-planning.svg) | brief to typed `ResearchPlan`; the window comes from a committed file, never from model output | ADR-019, `agents/planner.py` |
| P2 | [goal monitoring](p2-coverage-rounds.svg) | coverage scored per requirement, one bounded widened round, unmet requirements reported | ADR-020, `services/board.py` |
| P3 | [multi-agent](p3-specialist-agents.svg) | planner, researcher, auditor — separated by tool access, not by instruction | ADR-022, `agents/research.py` |
| P4 | [guardrails](p4-guardrails.svg) | SQL validation in the application, row policy in ClickHouse; two independent layers | ADR-013/014, `validate_analytical_query`, `sql/security/odyssey_mcp_role.sql` |
| P5 | [self-consistency](p5-self-consistency.svg) | three samples per passage, candidates matched on the span they claim | `pipelines/extraction/consistency.py` |
| P6 | [memory](p6-vocabulary-memory.svg) | productive search terms written back as reference data, and the evidence tables they never touch | ADR-021, `repositories/terms.py` |

## The workflows in full

Drawn from the code as built (2026-09-06, `feat/ui-redesign`) with the branches and
bounds included. Reference drawings for checking a claim against the code — dense by
design, not slides.

| # | Diagram | Workflow |
|---|---|---|
| 01 | [system topology](01-system-topology.svg) | where each part runs; the read-only MCP path and the separate admin write path |
| 02 | [board build](02-board-build.svg) | `POST /api/research` to a persisted board: plan, three retrieval paths, coverage, gap round, verification, timeline events |
| 03 | [corpus acquisition](03-corpus-acquisition.svg) | how a new source reaches the corpus: discovery, rights determination, staging, fidelity, promotion — **specified, not built** (Task 028) |

Each `.svg` has a matching `.png` at 2× for slides and READMEs.

## Legend

Box style is the encoding, and it repeats across every diagram:

- solid grey — deterministic code (a Python function; no model involved)
- solid blue — a model call (Gemini)
- solid red — a security boundary (query guardrail, ClickHouse row policy)
- dashed — a store (ClickHouse table, committed reference data)
- dotted — an external system (browser entry point, MCP server, Gemini, ClickHouse Cloud)
- pills — states; green = terminal outcome, red = blocked, refused, or discarded

Red arrows are failure or refusal paths; grey arrows are persistence and secondary flows.

A box with no edge reaching it is deliberate: see `sourcecut.observations` in P6, which is
the point of that diagram.

## Regenerating

```sh
node docs/diagrams/src/build.mjs          # all
node docs/diagrams/src/build.mjs 02 p4    # by filename fragment
```

`src/svg.mjs` is the builder; each `src/NN-*.mjs` and `src/pN-*.mjs` is one diagram. PNGs
need playwright (`npm i -g playwright && npx playwright install chromium`); without it the
script writes SVGs only and says so.
