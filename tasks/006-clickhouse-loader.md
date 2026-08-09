# Task 006 — ClickHouse Corpus Loader

## Goal

Load parsed entries, passages, and validated observations idempotently.

## Scope

- `clickhouse-connect` repository layer for this offline write path;
- bulk inserts;
- extraction run/failure records;
- skip already-processed passage/model/schema/prompt combinations.

## Acceptance criteria

- At least 100 demo passages can be loaded.
- Rerun does not duplicate trusted observations.
- Source records and hashes remain stable.
- No write or bulk-load operation is routed through the runtime MCP server.
