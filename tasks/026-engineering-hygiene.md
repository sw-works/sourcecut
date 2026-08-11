# Task 026 — Engineering Hygiene and Spec Reconciliation

## Goal

Close the small drift items found in review: duplicated test fakes, a spec'd-but-missing API
route, and documentation that no longer matches the built system.

## Read first
- `tests/test_corpus_repository.py`, `tests/test_clickhouse_migrations.py`,
  `tests/test_loc_media.py` (three separate `FakeClickHouseClient` definitions)
- `docs/hackathon-build/technical-spec.md` (API contract + repo layout sections)
- `apps/api/sourcecut_api/main.py`

## Scope

### Test consolidation

- Add `tests/conftest.py`; unify the three `FakeClickHouseClient` definitions into one
  configurable fake (they differ — reconcile capabilities, don't just pick one; each
  existing test keeps its exact assertions).
- Audit other duplicated fakes (`FakeMcpClient` variants) — consolidate only where the fake
  is genuinely identical in intent; do not force unrelated fakes together.

### API completeness

- Implement `GET /api/assets/{asset_id}` per `technical-spec.md` (top-level, not
  session-scoped): resolves from `media_assets` via the deterministic path, 404 on unknown,
  same thumbnail confinement rules as the session-scoped route. Or, if product direction
  prefers session-scoping only, amend the spec instead — decide, do one, document why.

### Documentation reconciliation

- `technical-spec.md` repo-layout section describes `routes/` and `tools/` packages that
  were never built — update to the actual layout (inline routes in `create_app`,
  `integrations/`, `services/`).
- Record the Task 014/016 physical-schema reality in `pipeline-spec.md`'s table list
  (engines, `entities`/`entity_mentions` now real via Task 020).
- README: bring the ClickHouse bootstrap section up to date with row policies (015),
  dictionary grant (019), and any new CLI entry points (`sourcecut-embed`,
  `sourcecut-eval`, loaders).
- `demo-plan.md`: refresh the minute-by-minute script to include one new marquee moment
  (recommended: the row-policy proof — agent literally cannot read unvalidated rows).

### Deferred-decision log

- Single place (`docs/hackathon-build/deferred.md`) recording items intentionally not done
  with their triggers: native full-text index (server version), `vector_similarity` index
  (corpus scale), JSON type conversion (server version), live Veo acceptance (budget
  approval), full media harvest (API keys/quota).

## Do not
- change runtime behavior beyond the one new route;
- rewrite history in task files 001–013 (they describe what was asked; summaries describe
  what happened).

## Acceptance criteria

1. `pytest` passes with `conftest.py` consolidation; net test LOC decreases; no assertion
   weakened.
2. `GET /api/assets/{asset_id}` (or the documented spec amendment) matches
   `technical-spec.md` exactly.
3. A fresh reader following README + runbooks alone can bootstrap, load, embed, evaluate,
   and demo without consulting git history (checklist run-through noted in summary).
4. `deferred.md` lists every open gated item with its unblocking condition.
