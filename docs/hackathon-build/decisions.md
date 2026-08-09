# Architecture Decision Log

## ADR-001 — Competition track
Status: Final

SourceCut targets the **ClickHouse** partner track.

ClickHouse must be central to runtime product behavior, not merely logging.

## ADR-002 — ClickHouse access
Status: Final

Use:

`Google ADK → typed Python tool → service/repository → clickhouse-connect → ClickHouse Cloud`

Do not use ClickHouse MCP.

Reasons:
- deterministic SQL;
- safer queries;
- easier testing;
- simpler observability;
- lower demo risk.

## ADR-003 — No arbitrary agent SQL
Status: Final

Gemini never emits arbitrary SQL for direct execution.

Agent tools expose semantic operations such as:
- `search_historical_evidence`;
- `compare_primary_sources`;
- `search_media_assets`;
- `get_passage`.

Application code owns SQL.

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
