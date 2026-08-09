# Gutenberg → Gemini → ClickHouse Pipeline Spec

## Data layers

1. Source manifest.
2. Immutable raw journal entries/passages.
3. AI-derived observations tied to exact evidence spans.
4. Runtime synthesis across observations.

## ClickHouse tables

Implement migrations for:
- `sources`;
- `journal_entries`;
- `passages`;
- `observations`;
- `entities`;
- `entity_mentions`;
- `extraction_runs`;
- `extraction_failures`;
- `research_events`.

### Key fields — journal entries

- `entry_id String`
- `source_id String`
- `author_id LowCardinality(String)`
- `author_display_name String`
- `entry_date Date`
- `ordinal_for_day UInt16`
- `heading String`
- `raw_text String`
- `source_url String`
- `source_locator String`
- `raw_text_sha256 FixedString(64)`
- `parser_version LowCardinality(String)`
- `ingested_at DateTime64(3, 'UTC')`

### Key fields — passages

- `passage_id String`
- `entry_id String`
- `source_id String`
- `author_id`
- `author_display_name`
- `entry_date`
- `passage_index`
- `char_start`
- `char_end`
- `passage_text`
- `passage_sha256`

Invariant:

`entry.raw_text[char_start:char_end] == passage_text`

## Initial observation categories

- weather
- terrain
- transportation
- food
- shelter
- equipment
- person
- animal
- place
- health
- event

## Observation contract

Each candidate contains:
- `category`;
- `canonical_term`;
- `normalized_description`;
- `explicit`;
- `source_quote`;
- `source_start`;
- `source_end`;
- `confidence`.

## Extraction instruction

Gemini must:
- extract only observations supported by the supplied passage;
- use no outside knowledge as evidence;
- preserve uncertainty;
- provide an exact contiguous source quote and offsets;
- return no observation when no relevant evidence exists.

## Validation

Before trusted insertion:
1. Pydantic schema validation.
2. source-end > source-start.
3. span in bounds.
4. exact substring equals `source_quote`.
5. category is allowed.
6. exact duplicate detection.

Invalid observations must not enter trusted research results.

## Idempotency key

Skip extraction when an existing run matches:

`passage_sha256 + model + schema_version + prompt_version`

## Retry policy

Retry transient failures only:
- timeouts;
- rate limits;
- 5xx;
- temporary network errors.

Suggested backoff: 1s, 3s, 8s; maximum 3 attempts.

Do not auto-retry semantic validation failures.

## ClickHouse access

Use a long-lived `clickhouse-connect` client managed by the application.

Agent tools call services/repositories; SQL remains in application code.

## First research queries

Support:
- date-range observations;
- term/category filtering;
- passage lookup;
- cross-author aggregation.

Example synthesis rule for MVP:
- >=2 distinct authors → `HIGH`;
- >=1 valid observation → `SINGLE_SOURCE`;
- later extend to conflicts/contextual evidence.

## First vertical slice

Use entries around September 9–30, 1805.

Priority concepts:
- snow/weather;
- horses/transportation;
- terrain;
- food scarcity;
- forest;
- camp/shelter;
- equipment;
- relevant places.

Manually review 50–100 important observations into a gold fixture.
