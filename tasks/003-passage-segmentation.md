# Task 003 — Passage Segmentation

## Goal

Convert journal entries into deterministic passages while preserving exact offsets.

## Rules

- Entry <= 6,000 chars: one passage.
- Longer entries: split at paragraph boundaries near 3,500–5,000 chars.
- Never cross entry/date/author boundaries.
- Preserve `char_start`, `char_end`, and passage hash.

## Acceptance criteria

For every passage:

`entry.raw_text[char_start:char_end] == passage_text`

Tests must reconstruct each parent entry exactly from passage spans.
