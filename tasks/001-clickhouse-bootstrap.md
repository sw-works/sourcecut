# Task 001 — ClickHouse Bootstrap

## Goal

Create the initial ClickHouse schema and connection layer.

## Read first
- `AGENTS.md`
- `docs/hackathon-build/decisions.md`
- `docs/hackathon-build/pipeline-spec.md`

## Scope

- Add migrations for `sources`, `journal_entries`, `passages`, `observations`, `extraction_runs`, `extraction_failures`, and `research_events`.
- Add a `clickhouse-connect` client factory.
- Add a migration/bootstrap command.
- Add migration idempotency tests.

## Do not
- add MCP;
- add agent logic;
- add media ingestion.

## Acceptance criteria

- Empty database bootstraps successfully.
- Bootstrap can be run twice without destructive failure.
- Test suite covers migration/bootstrap behavior.
- README documents exact bootstrap command.
