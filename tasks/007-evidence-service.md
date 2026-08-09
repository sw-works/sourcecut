# Task 007 — Historical Evidence Service

## Goal

Expose deterministic semantic queries over ClickHouse for API drill-down, evaluation, and
non-agent application paths.

## Functions

- get observations by date/category/term;
- cross-author comparison;
- passage lookup;
- evidence grouping by canonical term.

## Rules

- direct repositories accept no arbitrary SQL input; agent-generated analytical SQL belongs only
  in the read-only MCP path introduced by Task 008;
- only `validation_status='valid'` observations by default.

## Acceptance criteria

A September 1805 query returns structured evidence grouped across Lewis/Clark with source passages.
