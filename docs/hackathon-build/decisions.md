# Architecture Decision Log

## ADR-001 — Competition track
Status: Final

SourceCut targets the **ClickHouse** partner track.

ClickHouse must be central to runtime product behavior, not merely logging.

The user-facing research flow must actively access ClickHouse through the official
`mcp-clickhouse` server.

## ADR-002 — ClickHouse access
Status: Superseded by ADR-013

Former runtime decision:

`Google ADK → typed Python tool → service/repository → clickhouse-connect → ClickHouse Cloud`

This direct runtime path is retained only for offline ingestion and administrative work. The
earlier prohibition on ClickHouse MCP is superseded by ADR-013.

Reasons retained for the offline/admin path:
- deterministic SQL;
- safer queries;
- easier testing;
- simpler observability;
- lower demo risk.

## ADR-003 — No arbitrary agent SQL
Status: Amended by ADR-013

Gemini never emits SQL for direct execution by application repositories.

Application-owned deterministic tools continue to expose operations such as:
- `search_historical_evidence`;
- `compare_primary_sources`;
- `search_media_assets`;
- `get_passage`.

Application code owns SQL.

For runtime research, Gemini may generate analytical SQL through the official
`mcp-clickhouse.run_query` tool under ADR-013's read-only, least-privilege, schema-pattern, and
table-scope constraints.

## ADR-004 — Evidence boundary
Status: Final

Gemini background knowledge may guide search, but it is never evidence.

Every historical claim shown in a board must resolve to stored evidence records and source passages.

If evidence is missing, return that it is unsupported.

## ADR-005 — Exact evidence spans
Status: Final

Every AI-derived primary-source observation stores:
- exact contiguous source quote;
- zero-based character start/end offsets;
- passage hash;
- model/prompt/schema version.

The application validates the span before marking an observation trusted.

## ADR-006 — Raw text immutability
Status: Final

Original journal text is never rewritten by AI. Derived layers are regenerable.

## ADR-007 — Initial journal corpus
Status: Final

Use Project Gutenberg eBook 8419 as the initial distributable public-domain Lewis/Clark text corpus.

Treat the University of Nebraska Lewis & Clark Journals site as a scholarly validation/reference source, not as a redistributable corpus.

## ADR-008 — Media sources
Status: Final

Priority:
1. Library of Congress — maps, manuscripts, historical imagery.
2. Smithsonian Open Access — CC0 material culture/natural history.
3. National Park Service — modern/reconstructed/environmental references with per-item rights checks.

## ADR-009 — External API dependency
Status: Final

Harvest and cache archive metadata/media before the demo. Live research should run against the local/ClickHouse corpus and must not require archive APIs to be available.

## ADR-010 — Grafana
Status: Final

Grafana is a supporting observability layer via OpenTelemetry.

Track:
- ingestion;
- Gemini extraction;
- ClickHouse query latency;
- ClickHouse MCP tool calls, query latency, row counts, and failures separately from direct queries;
- ADK tool calls;
- research traces;
- invalid evidence spans;
- errors;
- evidence coverage.

Grafana is not the core evidence datastore.

## ADR-011 — Scale
Status: Final

Do not fabricate historical facts to increase row count.

Scale can come from:
- granular observations;
- media annotations;
- research events;
- ingestion/agent telemetry;
- synthetic operational events only where clearly non-historical.

## ADR-012 — Frontend/backend
Status: Superseded by ADR-018

- Former frontend: Next.js + TypeScript.
- Backend: FastAPI + Python.
- Deployment: Google Cloud Run for backend.

Boring, reliable choices are preferred over novel infrastructure.

## ADR-013 — Official ClickHouse MCP runtime
Status: Final

The user-facing research path is:

`Google ADK → ClickHouse MCP client/tool adapter → official mcp-clickhouse → ClickHouse Cloud`

The agent may use `list_databases`, `list_tables`, and `run_query`. Analytical SQL generation is
allowed only through `run_query` and is constrained by:

- a dedicated least-privilege read-only ClickHouse user;
- grants limited to the SourceCut database/tables;
- `CLICKHOUSE_ALLOW_WRITE_ACCESS=false`;
- documented SourceCut schema and approved query patterns;
- query timeouts and telemetry;
- authenticated HTTP transport for hosted environments.

Authentication may be disabled only for non-public local development. Direct
`clickhouse-connect` remains approved for ingestion, migrations, bulk loading, evaluation setup,
and administrative jobs. Deterministic application services continue to own exact passage lookup,
evidence-span validation, and all writes.

Reference: [official ClickHouse MCP server](https://github.com/ClickHouse/mcp-clickhouse).

## ADR-018 — Astro static-first frontend
Status: Final

The web application uses Astro with React islands:

- public landing, corpus navigation, all 24 Odyssey book routes, and curated entity routes are
  prerendered;
- existing React research tools hydrate only on the routes that need them;
- shared-board token routes and the same-origin API gateway render on demand through the Astro
  Node adapter;
- FastAPI remains the runtime service for agent research, analytical search, claims, boards,
  exports, shares, and curation;
- user-facing runtime research continues to use the official `mcp-clickhouse` path under ADR-013.

This preserves the evidence boundary while allowing immutable public material to move into static
release artifacts without coupling ordinary page delivery to ClickHouse or MCP latency.

## ADR-014 — Database-enforced evidence boundary
Status: Final

The trusted-evidence filter moves from application `WHERE` clauses and prompt text into
ClickHouse itself:

- a `ROW POLICY` on `sourcecut.observations` (and later `entity_mentions`) restricts
  `sourcecut_mcp_role` to `trusted = true AND validation_status = 'valid'` rows;
- approved query patterns are encoded as parametrized views granted to the MCP role;
- the application validator remains as defense in depth, not as the boundary.

Consequence: model-generated SQL through `run_query` physically cannot read unvalidated
evidence, regardless of prompt adherence. Because ClickHouse hides all rows of a policied
table from users not named in any policy on it, every restrictive policy ships with a
companion `USING 1 TO ALL EXCEPT sourcecut_mcp_role` policy that keeps admin/ingestion roles
unrestricted. The runtime views additionally filter trusted rows directly, so the boundary
holds even where the console policies were never applied (local development).

## ADR-015 — Embeddings are retrieval guidance, never evidence
Status: Final

Passages and media assets carry `Array(Float32)` embeddings in ClickHouse; retrieval may rank
by `cosineDistance`. Constraints:

- a similarity score may surface a passage but never appears as evidence and never changes a
  confidence label by itself;
- every displayed historical claim still requires a quote-anchored trusted observation
  (ADR-004/ADR-005 unchanged);
- brute-force ranking only at current scale; the experimental `vector_similarity` index is
  deferred until corpus size demands it;
- embedding writes use the direct admin path; runtime similarity queries run through
  read-only MCP `run_query`.

## ADR-016 — ClickHouse is the system of record for sessions and agent events
Status: Final

Research sessions and agent/tool events persist in `research_sessions` /
`research_events` (with an AggregatingMergeTree rollup for dashboards), replacing the
in-process session dict. The API becomes horizontally scalable; the SSE timeline replays real
events. Operational rows are non-historical data per ADR-011 and never mix with evidence
tables. No queue or external state store is introduced (ADR-012: boring).

## ADR-017 — Curated reference data class
Status: Final

A third data class exists alongside evidence and operational data: **curated reference data**
(term-expansion vocabulary, entity registry, route waypoints). Rules:

- committed to the repo as human-editable JSON, loaded idempotently;
- may guide retrieval and rendering; never displayed as a historical claim;
- where it asserts anything about the past (entity identities, route coordinates), each item
  carries citations or a named scholarly source in the data file;
- readable through MCP like other tables; written only via loaders on the admin path.

## ADR-019 — The model plans; the application retrieves
Status: Final

The research agent decides *what to investigate*; deterministic application code decides *what
the corpus says*. Concretely:

- a planner turns the filmmaker's brief into a typed `ResearchPlan` — scope, production
  requirements, period search vocabulary — and nothing else;
- the plan's date window is not model output. The planner selects a `scope_id` from
  `data/reference/research_scopes.json` and the window is read from that file, so a plan cannot
  widen the corpus slice or invent a period;
- plan fields are validated before use: known scope, allowed categories, bounded requirement and
  term counts, and a restricted term charset, because terms reach SQL as literals;
- planning degrades rather than fails. Deterministic keyword routing over the same scope file
  backs the model planner and takes over when a plan fails validation or the model is
  unavailable, so the board path runs with no credential configured;
- a plan is never evidence. Every displayed claim still resolves to a stored, validated passage
  (ADR-004/ADR-005).

## ADR-020 — Bounded goal-directed research rounds
Status: Final

Each planned requirement carries its own success criterion. After retrieval, coverage is scored
per requirement and reported on the board, including what the corpus did not support.

Unmet requirements trigger at most one additional round (`SOURCECUT_RESEARCH_ROUNDS`, default 2
total). A round widens only the vocabulary of the requirements that failed and re-queries the
same window; it never widens the window, lowers a success criterion, or retries indefinitely.

Gap-round evidence is passage-derived and keeps `passage-term:` citation ids, so it stays
distinguishable from validated observations. Unmet coverage is displayed, not hidden: a board
that could not support a requirement says so.

## ADR-021 — Retrieval vocabulary is learned; evidence is not
Status: Final

Search terms that a gap round proves productive are written back to `term_expansions` with
`provenance='discovered'`, so later sessions start with vocabulary earlier ones had to find.

This is the only feedback loop in the system, and it is deliberately confined to curated
reference data (ADR-017). It changes what SourceCut looks for, never what SourceCut believes:
no observation, confidence label, or citation is ever derived from it. Curated rows keep their
provenance and only gain terms, so a curator can distinguish and reverse discovered vocabulary.
Memory failures are non-fatal — a board is never lost because vocabulary could not be persisted.

## ADR-022 — Specialist agents separated by tool access
Status: Preferred

The ADK research runtime offers a three-stage sequence (`sourcecut-research --pipeline`):
planner, researcher, auditor. Separation is enforced by tools, not by instructions alone.

- The planner has no tools, so it cannot reach the corpus and cannot smuggle a claim in as a plan.
- The researcher holds the ClickHouse MCP tools under the existing `run_query` guardrail.
- The auditor has no tools and sees only what the researcher returned, so it can find claims that
  outran their citations but cannot fetch new evidence to justify them.

Stages hand off through named output keys rather than a shared scratchpad. The single-agent
runtime remains the default; the sequence is opt-in while it is exercised.
