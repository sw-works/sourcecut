# Task 014 — ClickHouse Physical Schema Hardening

## Goal

Move text search, point lookup, retention, and compression from "works at demo scale" to
engine-native ClickHouse features: token bloom-filter skip indexes, a passage-id projection,
TTL on telemetry, and column codecs.

## Read first
- `AGENTS.md`
- `docs/hackathon-build/decisions.md`
- `sql/clickhouse/` (all applied migrations)
- `apps/api/sourcecut_api/db/migrations.py` (runner applies exactly one statement per file)

## Background

Current state (verified):
- Every table is plain `MergeTree` with zero skip indexes, zero codecs, zero TTL.
- Text search uses `positionCaseInsensitiveUTF8` substring scans
  (`repositories/evidence.py`, `services/board.py`, `agents/research.py` instruction,
  `integrations/clickhouse_mcp.py` preflight). No index can accelerate that function.
- `get_passage` filters `WHERE passage_id = ...` but `passage_id` is the **last** element of
  the `passages` sort key, so every point lookup scans the table.
- `research_events` has no TTL and is the only unbounded time-series table.

## Scope

### Migrations (one statement per file, numbered from `012_`)

1. `ALTER TABLE passages ADD INDEX idx_passage_text_tokens passage_text
   TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 4;`
2. `ALTER TABLE passages MATERIALIZE INDEX idx_passage_text_tokens;`
3. Same pair for `media_assets` over `title` and `description` (one combined index over
   `concat`-free multi-column syntax is not available; add one index per column or a single
   index on `title` if measurement shows `description` rarely filters).
4. `ALTER TABLE passages ADD PROJECTION by_passage_id (SELECT * ORDER BY passage_id);`
5. `ALTER TABLE passages MATERIALIZE PROJECTION by_passage_id;`
6. `ALTER TABLE research_events MODIFY TTL occurred_at + INTERVAL 90 DAY;`
7. Codecs, each in its own migration:
   - `passages.passage_text` → `CODEC(ZSTD(3))`
   - `journal_entries.raw_text` → `CODEC(ZSTD(3))`
   - `passages.entry_date`, `journal_entries.entry_date` → `CODEC(Delta, ZSTD)`
   - `DateTime64` audit columns on high-row tables → `CODEC(Delta, ZSTD)`

### Query changes

- Term-count and term-presence queries switch from
  `positionCaseInsensitiveUTF8(passage_text, t) > 0` to
  `hasTokenCaseInsensitive(passage_text, t)` so the tokenbf index prunes granules:
  `repositories/evidence.py`, `services/board.py` (`EVIDENCE_QUERY`, `PASSAGE_EVIDENCE_QUERY`,
  `MEDIA_QUERY` where applicable), `integrations/clickhouse_mcp.py` preflight query,
  `agents/research.py` approved patterns.
- Token semantics differ from substring semantics (`hasToken` matches whole tokens; it will
  not match `snows` when searching `snow`). Where the current behavior depends on substring
  matching, keep `positionCaseInsensitiveUTF8` and say so in a comment; do not silently change
  match semantics for the evidence filter without a test proving result parity on the Sept
  1805 corpus, or an explicit accepted difference documented in the task summary.
- `get_passage` (MCP fixed query) and `repositories/evidence.py` point lookup stay
  syntactically identical; the projection accelerates them without query changes.

### Explicitly deferred in this task

- Native full-text index (`TYPE text`/inverted): still version-sensitive; evaluate the
  deployed ClickHouse Cloud version and record a follow-up note in the task summary. Do not
  apply it in this task.
- Converting `raw_metadata`/`payload_json` `String` columns to the native `JSON` type:
  requires a server-version check and a table rebuild; fold into the Task 016 rebuild if the
  deployed version supports GA `JSON`, otherwise record as deferred.
- Re-adding partitioning (lost when `entry_date` became `Int32` in migrations 008/009):
  fold into the Task 016 table rebuild (`PARTITION BY intDiv(entry_date, 10000)`).

## Do not
- change any table engine (Task 016);
- add row policies or views (Task 015);
- add embedding columns (Task 018);
- touch MCP server deployment or grants.

## Acceptance criteria

1. Fresh database bootstraps cleanly; re-running bootstrap is a no-op; migration ledger test
   updated for the new files.
2. `EXPLAIN indexes = 1` on the term-count query shows the tokenbf index pruning granules
   (documented in the task summary with the actual EXPLAIN output).
3. `EXPLAIN` on the `passage_id` point lookup shows the projection being chosen.
4. `SHOW CREATE TABLE research_events` shows the TTL clause.
5. All existing unit tests pass; any query whose match semantics changed has a test asserting
   the new behavior on fixture text.
6. `sourcecut-mcp-preflight` still passes end to end against a loaded database.
