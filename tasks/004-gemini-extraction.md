# Task 004 — Gemini Structured Observation Extraction

## Goal

Extract production-relevant historical observations from passages using schema-constrained Gemini output.

## Categories

weather, terrain, transportation, food, shelter, equipment, person, animal, place, health, event

## Output fields

- category
- canonical_term
- normalized_description
- explicit
- source_quote
- source_start
- source_end
- confidence

## Constraints

- no outside knowledge as evidence;
- exact contiguous source span required;
- preserve uncertainty;
- no inferred historically plausible objects;
- Pydantic v2 validation.

## Acceptance criteria

- One passage can be processed into typed candidates.
- Model/prompt/schema versions are recorded.
- Extraction is idempotent by passage hash + model + schema + prompt version.
