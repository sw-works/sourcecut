# Task 015 — Database-Enforced Evidence Boundary

## Goal

Move the core invariant — the research agent can only ever read validated evidence — from
application-side `WHERE` clauses and prompt text into ClickHouse itself, using a row policy on
the MCP role and parametrized views that encode the approved query patterns.

## Read first
- `AGENTS.md`
- `docs/hackathon-build/decisions.md` (ADR-004, ADR-013, new ADR-014)
- `README.md` ClickHouse database users section
- `apps/api/sourcecut_api/agents/research.py` (validator + instruction)
- `integrations/clickhouse_mcp.py` (preflight)

## Background

Today `trusted = true AND validation_status = 'valid'` is a convention: it appears in
`repositories/evidence.py`, `services/board.py`, and the agent prompt. Nothing stops a
model-generated `run_query` from reading unvalidated observation candidates. The approved
query patterns live only as prose in the prompt plus a regex validator.

## Scope

### Row policy (SQL console block, not a migration)

The migration runner authenticates as `sourcecut_admin`, which has no ACCESS MANAGEMENT
privileges, so policy DDL joins the existing role/user block in `README.md` that is run as the
ClickHouse Cloud console admin:

```sql
CREATE ROW POLICY IF NOT EXISTS sourcecut_trusted_observations
ON sourcecut.observations
FOR SELECT
USING trusted = true AND validation_status = 'valid'
TO sourcecut_mcp_role;
```

Once any permissive row policy exists on a table, users not named in some policy on that
table see zero rows — so every restrictive policy needs a companion
`USING 1 TO ALL EXCEPT sourcecut_mcp_role` policy to keep `sourcecut_admin` and ingestion
unrestricted. Document that semantics note in the README block.

### Parametrized views (regular migrations — `sourcecut_admin` has CREATE)

One statement per migration file:

1. `sourcecut.evidence_window(start Int32, end Int32, limit UInt16)` — the join of `passages`
   and `observations` currently duplicated between `repositories/evidence.py:56-90` and
   `services/board.py:54-78`, with the date predicate as parameters.
2. `sourcecut.author_term_presence(start Int32, end Int32, term String)` — per-author
   `hasTokenCaseInsensitive` counts over `passages` (the preflight/demo comparison query).
3. `sourcecut.passage_lookup(pid String)` — the fixed `get_passage` query.

The existing `GRANT SELECT ON sourcecut.*` to `sourcecut_mcp_role` already covers new views;
verify rather than re-grant.

### Application/agent changes

- `services/board.py` and `integrations/clickhouse_mcp.py` issue `SELECT * FROM
  sourcecut.evidence_window(start=..., end=..., limit=...)`-style calls through MCP
  `run_query` instead of inline SQL. (`SELECT *` from a parametrized view is acceptable;
  adjust the validator accordingly — see next point.)
- `agents/research.py`:
  - instruction rewrites the approved patterns section around the views: prefer views for the
    standard questions, raw `SELECT` still allowed for novel analysis under existing rules;
  - `validate_analytical_query` gains a view-call branch: allow `FROM
    sourcecut.<view>(...)` for the allowlisted view names, keep every other rule
    (single statement, no mutation keywords, `LIMIT`, date bound for raw table reads).
- `repositories/evidence.py` may keep its direct-path SQL (admin path is not the boundary),
  but switch it to the same view to kill the duplicated join if convenient.

### Preflight additions (`run_mcp_preflight`)

- Insert (via direct admin path, or reuse a fixture row) one observation with
  `trusted = false`; assert an unfiltered `SELECT count() FROM sourcecut.observations` through
  MCP does not count it, proving the policy, then clean up.
- Assert `evidence_window` and `author_term_presence` return rows through MCP.

## Do not
- weaken any existing validator rule for raw table queries;
- give the MCP role any new table privileges;
- move writes anywhere near MCP;
- create policies for roles other than `sourcecut_mcp_role`.

## Acceptance criteria

1. With the policy applied, an MCP `run_query` reading `observations` **without** any
   `trusted` filter returns only validated rows; the same query on the direct admin path
   returns all rows. Both asserted by preflight or an opt-in integration test.
2. Board assembly produces an identical board before/after the switch to views on the
   canonical Sept 1805 prompt (byte-stable JSON comparison, minus timestamps).
3. Validator unit tests cover: allowed view call, view call with unknown view rejected, raw
   table rules unchanged.
4. README documents the policy in the console SQL block with the role-scoping note.
5. `docs/hackathon-build/decisions.md` gains ADR-014 marked Final.
