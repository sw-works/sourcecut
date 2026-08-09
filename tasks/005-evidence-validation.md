# Task 005 — Evidence Validation

## Goal

Prevent unsupported model output from entering trusted observations.

## Validation

- valid span order;
- in bounds;
- exact substring equals `source_quote`;
- allowed category;
- confidence range;
- exact duplicate rejection.

## Acceptance criteria

- Deliberately corrupted offsets are rejected.
- Deliberately corrupted quote is rejected.
- Invalid observations never appear in trusted research queries.
- Extraction failures remain inspectable.
