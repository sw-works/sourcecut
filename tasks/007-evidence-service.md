# Task 007 — Historical Evidence Service

## Goal

Expose deterministic semantic queries over ClickHouse.

## Functions

- get observations by date/category/term;
- cross-author comparison;
- passage lookup;
- evidence grouping by canonical term.

## Rules

- no arbitrary SQL input;
- only `validation_status='valid'` observations by default.

## Acceptance criteria

A September 1805 query returns structured evidence grouped across Lewis/Clark with source passages.
