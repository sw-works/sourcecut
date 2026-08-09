# Task 006 — ClickHouse Corpus Loader

## Goal

Load parsed entries, passages, and validated observations idempotently.

## Scope

- repository layer;
- bulk inserts;
- extraction run/failure records;
- skip already-processed passage/model/schema/prompt combinations.

## Acceptance criteria

- At least 100 demo passages can be loaded.
- Rerun does not duplicate trusted observations.
- Source records and hashes remain stable.
