# Task 016 — Engine-Native Idempotency with ReplacingMergeTree

## Goal

Replace application-side duplicate avoidance (pre-querying existing ids/hashes before every
batch insert) with `ReplacingMergeTree`, making reloads idempotent by engine semantics.

## Read first
- `tasks/014-clickhouse-physical-schema.md` (deferred items folded into this rebuild)
- `apps/api/sourcecut_api/repositories/corpus.py` (`existing ids` probes around lines 401–456)
- `apps/api/sourcecut_api/repositories/media.py` (probe around lines 91–115)
- `sql/clickhouse/008_historical_entry_dates.sql` / `009_...` (the `CREATE OR REPLACE` rebuild
  pattern this task reuses)

## Background

All row ids are already deterministic (sha256-derived — `corpus.py` id builders, LOC asset
ids), which is exactly the shape `ReplacingMergeTree` wants: same id → same logical row;
newest version wins. Current loaders instead run existence probes and filter in Python.
Replacing dedups only at merge time within a part family, so readers must use `FINAL` (cheap
at this corpus size) — that is the one behavioral cost and it must be explicit in every
reader.

## Scope

### Table rebuilds (`CREATE OR REPLACE TABLE`, one per migration file)

Rebuild with `ENGINE = ReplacingMergeTree(<version column>)`, same ORDER BY keys, plus the
Task 014 deferrals:

| Table | Version column | Also in this rebuild |
|---|---|---|
| `journal_entries` | `ingested_at` (exists) | `PARTITION BY intDiv(entry_date, 10000)`; codecs from 014 carried over |
| `passages` | `ingested_at` (exists) | same partition key; tokenbf index + projection re-declared in the CREATE |
| `observations` | `created_at` (exists) | — |
| `media_assets` | `harvested_at`/equivalent existing timestamp; add one if absent | — |

Note: `CREATE OR REPLACE` drops data. The corpus is fully regenerable by documented loaders
(ADR-006); the task summary must include the exact reload sequence executed
(`sourcecut-load-gutenberg` → extraction → validation load → `python -m pipelines.media`).
If the deployed server supports the GA `JSON` type, convert `raw_metadata` columns in the
same rebuild; otherwise leave `String` and record the version blocking it.

The ORDER BY keys must uniquely identify a logical row for Replacing semantics to be correct.
Verify per table before writing the migration: every current ORDER BY ends in the unique id
(`entry_id`, `passage_id`, `observation_id`, `asset_id`), which satisfies this.

### Reader changes

Every SELECT against the rebuilt tables adds `FINAL` (or an equivalent `argMax` aggregation
where `FINAL` is awkward):
- `repositories/evidence.py`, `repositories/corpus.py` probes that remain, `repositories/media.py`;
- `services/board.py` MCP query constants and the Task 015 views (`evidence_window` etc. —
  update the view definitions in a follow-on migration; a view baking in `FINAL` keeps the
  agent's raw queries correct without the agent knowing about it);
- `agents/research.py` instruction: document that tables are Replacing and views already
  handle versions; raw queries on base tables should either use `FINAL` or accept
  possible-but-rare duplicate rows (state which).

### Loader simplification

- Delete the existence-probe/dedup code paths in `corpus.py` and `media.py`; insert
  unconditionally. Keep the content-hash short-circuit **only** where it saves a paid Gemini
  call (extraction idempotency keys stay — those are about API cost, not row dedup).
- Keep async_insert settings as-is.

## Do not
- change ids or hashing;
- introduce `OPTIMIZE ... FINAL` calls in application code (readers use `FINAL`; merges
  happen when they happen);
- touch `extraction_runs`/`extraction_failures`/`research_events` (append-only logs stay
  plain `MergeTree`).

## Acceptance criteria

1. Running the full ingestion sequence twice back-to-back yields identical `count()` per
   table via `FINAL` reads, with zero Python-side dedup probes executed (assert by log or by
   code removal).
2. `SELECT count()` with and without `FINAL` after a double load differ (proving the engine,
   not the loader, is deduplicating) — shown in the task summary.
3. Board output on the canonical prompt is unchanged.
4. Unit tests: fake-client tests updated; a test proving reader queries include `FINAL`.
5. Migration ledger tests updated; bootstrap idempotent from empty.
