# Task 017 — Durable Research Sessions and Real Agent Timeline

## Goal

Make ClickHouse the system of record for research sessions and agent events: write
`research_events` (currently a table nobody reads or writes), persist session/board state so
the API survives restarts and can scale past one instance, drive the SSE timeline from real
events instead of the scripted five stages, and roll events up for Grafana with an
AggregatingMergeTree materialized view.

## Read first
- `apps/api/sourcecut_api/main.py` (`_run_session`, in-memory `dict` session store)
- `sql/clickhouse/007_research_events.sql`
- `apps/api/sourcecut_api/agents/research.py` (`_observe_adk_tool` callback)
- `deploy/cloud-run/README.md` (the `--min 1 --max 1` constraint this task removes)
- `docs/hackathon-build/decisions.md` (ADR-010, ADR-011, new ADR-016)

## Background

- Session state lives in `main.py`'s process dict; Cloud Run is pinned to a single instance
  because of it.
- The SSE timeline emits five hardcoded stage strings around one `build_board()` call.
- `research_events` exists, is migrated and tested, and has zero readers/writers.
- All writes stay on the direct `clickhouse-connect` admin path per ADR-013; MCP remains
  read-only. Event/session writes are operational data, not historical evidence (ADR-011
  explicitly blesses research events as a scale dimension).

## Scope

### New table + view (migrations)

1. `research_sessions` — `ReplacingMergeTree(updated_at)`, `ORDER BY session_id`. Columns:
   `session_id String`, `status LowCardinality(String)`, `prompt String`,
   `board_json String DEFAULT ''`, `error String DEFAULT ''`,
   `created_at`/`updated_at DateTime64(3,'UTC')`. Status transitions are whole-row upserts;
   readers use `FINAL`.
2. Materialized view `research_stage_stats_mv` → `AggregatingMergeTree` target table
   `research_stage_stats`, keyed `(event_type, stage, toStartOfHour(occurred_at))`, storing
   `countState()`, `avgState(duration_ms)`, `quantilesState(0.5, 0.95)(duration_ms)`.
   Requires adding `duration_ms UInt32 DEFAULT 0` to `research_events` (ALTER migration)
   or deriving duration at write time — add the column; events are written by us.

### Event writer

- `ResearchEventRepository` (repositories/, direct path): `record(event)` insert with
  `async_insert=1, wait_for_async_insert=0` (fire-and-forget telemetry rows);
  session upserts use `wait_for_async_insert=1` (state must be durable before the API
  answers).
- Emit events from:
  - session lifecycle in `main.py` (`session_created`, `stage_started`, `stage_completed`,
    `board_completed`, `session_failed`);
  - `build_board()` real steps (evidence query issued/returned row counts, media query,
    verification outcomes, fallback-path taken — the fallback event matters: the committed
    demo brief proves the fallback ran without anyone noticing);
  - `_observe_adk_tool` in `research.py`: alongside the OTel span, insert an
    `mcp_tool_call` event (redacted SQL, row count, duration, access path).

### API changes

- Session store becomes ClickHouse-backed with the process dict demoted to a read-through
  cache. `GET /api/research/{id}` and the SSE endpoint read from the repository, so any
  instance can serve any session.
- SSE endpoint tails `research_events` for the session (poll loop stays; it now polls the
  table with `occurred_at > last_seen` instead of the in-memory list) and terminates on the
  session row reaching `complete`/`failed`.
- The five scripted stages are deleted; the timeline renders whatever events actually
  happened. Frontend `page.tsx` timeline copy updated to render event types generically.

### Deploy + observability

- `deploy/cloud-run/README.md`: raise `sourcecut-api` to `--max 3` and delete the in-memory
  caveat; document that session affinity is no longer needed.
- Grafana: document (or commit dashboard JSON if a dashboards dir exists) panels reading
  `research_stage_stats` with `countMerge`/`avgMerge`/`quantilesMerge` — closes the ADR-010
  MCP-vs-direct tracking item from real data instead of spans only.

## Do not
- write events or sessions through MCP;
- put board evidence content in event payloads (ids, counts, redacted SQL only — same
  redaction rules as telemetry `sanitize_sql`);
- introduce a message queue or any infra beyond ClickHouse (ADR-012: boring).

## Acceptance criteria

1. Start a research session, kill and restart the API process mid-run or after completion:
   `GET /api/research/{id}` returns the same status/board from the new process. (Integration
   test with a live local ClickHouse, or a unit test against the repository with the fake
   client plus a documented manual check.)
2. SSE timeline for the canonical prompt shows real events including at least one
   `mcp_tool_call` with a row count, and shows a `fallback` event if and only if the
   passage-fallback path ran.
3. `research_stage_stats` returns merged counts/latencies after a session
   (`countMerge` query shown in task summary).
4. Two concurrent API instances (or two app objects in one test process) both serve the same
   session correctly.
5. `research_events` TTL from Task 014 still present after the ALTER.
6. Unit tests for the repository, event emission points, and SSE tailing against fakes.
