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
Status: Preferred

- Frontend: Next.js + TypeScript.
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

## ADR-014 — Database-enforced evidence boundary
Status: Final

The trusted-evidence filter moves from application `WHERE` clauses and prompt text into
ClickHouse itself:

- a `ROW POLICY` on `sourcecut.observations` (and later `entity_mentions`) restricts
  `sourcecut_mcp_role` to `trusted = true AND validation_status = 'valid'` rows;
- approved query patterns are encoded as parametrized views granted to the MCP role;
- the application validator remains as defense in depth, not as the boundary.

Consequence: model-generated SQL through `run_query` physically cannot read unvalidated
evidence, regardless of prompt adherence. Admin/ingestion roles are unaffected (row policies
bind only to the roles they name).

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
