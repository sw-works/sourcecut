# Task 020 — Entities and Entity Mentions

## Goal

Implement the `entities` / `entity_mentions` layer specified in
`docs/hackathon-build/pipeline-spec.md` but never built: a curated entity registry (people,
places, tribes, animals, objects) plus quote-anchored mentions extracted per passage, enabling
"show every Sacagawea mention across authors" style queries.

## Read first
- `docs/hackathon-build/pipeline-spec.md` (original `entities`/`entity_mentions` field lists)
- `pipelines/extraction/gemini.py` + `pipelines/extraction/validation.py` (extraction +
  span-validation patterns to reuse verbatim)
- `tasks/019-term-expansion-dictionary.md` (alt-spelling machinery this layer shares)

## Background

Cross-author comparison is a stated core capability; today it is only term counts. Entities
give it a spine. The same evidence rules apply unchanged: a mention is trusted only if its
quote+offsets validate against the stored passage (ADR-005); the curated registry itself is
reference data, not historical claims.

## Scope

### Migrations

1. `entities` — `ReplacingMergeTree(updated_at)`, `ORDER BY entity_id`:
   `entity_id String` (slug), `entity_type LowCardinality(String)`
   (`person|place|tribe|animal|plant|object|event`), `canonical_name String`,
   `alt_names Array(String)`, `notes String`, `updated_at DateTime64(3,'UTC')`.
2. `entity_mentions` — `ReplacingMergeTree(created_at)`,
   `ORDER BY (entity_id, entry_date, passage_id, mention_id)`:
   `mention_id String` (sha256-derived, deterministic), `entity_id`, `passage_id`,
   `entry_date Int32`, `author_id LowCardinality(String)`, `source_quote String`,
   `source_start UInt32`, `source_end UInt32`, `trusted Bool DEFAULT false`,
   `validation_status LowCardinality(String) DEFAULT 'invalid'`, model/prompt/schema version
   columns matching `observations`, `created_at`.

### Registry seeding

- `data/reference/entities.json`, committed, human-curated: core expedition members,
  Sacagawea (with journal spelling variants in `alt_names`), York, Old Toby, the Shoshone and
  Salish/Flathead peoples, Bitterroot landmarks (Lolo Trail, Travelers' Rest, Lost Trail
  Pass), horses, key flora/fauna. Every `alt_names` variant must be an attested journal
  spelling — cite at least one passage per entity in `notes` where practical.
- Loader CLI `sourcecut-load-entities`.

### Mention extraction

- Extend the Gemini extraction pipeline with a second response schema
  (`EntityMentionBatch`): given a passage and the registry slice (names + alt names), emit
  quote-anchored mention candidates. New prompt version string; temperature 0; idempotency
  key includes registry content hash.
- Validation: reuse the existing span validator unchanged (quote match, offsets, bounds,
  duplicates) before `trusted=true, validation_status='valid'`.
- Deterministic pre-pass: exact `alt_names` string hits found by code (not the model) are
  auto-candidates with code-derived offsets — cheaper, and validates the model against a
  floor. Provenance column distinguishing `extractor: code|gemini`.

### Query surface

- Task 015-style parametrized view `entity_mentions_window(entity Ident/String, start, end)`
  joining mentions → passages, trusted-only via the same row-policy approach
  (`CREATE ROW POLICY ... ON sourcecut.entity_mentions ... TO sourcecut_mcp_role` in the
  README console block).
- API: `GET /api/entities` (registry), `GET /api/entities/{entity_id}/mentions?start=&end=`
  (through MCP at runtime, matching `get_passage` conventions).
- Agent: tables + view added to allowlist; instruction gains entity query patterns.
- UI (minimal in this task): passage inspector shows entity chips for trusted mentions;
  full cross-author UI is Task 021.

## Do not
- let Gemini invent entities not in the registry (unknown-name candidates are recorded as
  `extraction_failures`-style rejects for later curation, never auto-added);
- treat registry notes as displayable historical claims;
- build the comparison UI here (Task 021).

## Acceptance criteria

1. Registry + mentions load idempotently; rerun produces no new rows (`FINAL` counts equal).
2. For the Sept 1805 window, "Old Toby" (or chosen equivalent) returns trusted mentions from
   ≥2 authors with valid quote offsets, via MCP.
3. A corrupted-offset mention is rejected by validation and inspectable as a failure.
4. Code-extractor floor: every exact alt-name occurrence in the window has a mention row.
5. Unit tests: schema parse, span validation reuse, deterministic ids, registry loader,
   API endpoints against fakes.
