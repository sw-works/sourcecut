# Task 002 — Gutenberg Journal Parser

## Goal

Download/read Gutenberg 8419 and deterministically parse Lewis/Clark journal entries.

## Scope

- Implement source wrapper/header/footer removal.
- Parse `[Lewis|Clark, Month DD, YYYY]` headings.
- Preserve repeated same-date entries using `ordinal_for_day`.
- Preserve raw historical spelling/capitalization.
- Compute SHA-256 for raw entries.
- Add fixtures and parser tests for September 1805.

## Acceptance criteria

- Sampled September 1805 author/date boundaries are 100% correct.
- Same input produces byte-equivalent normalized entries every run.
- No historical text modernization occurs.
