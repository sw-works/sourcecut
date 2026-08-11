# Task 019 — Term-Expansion Dictionary

## Goal

Move the hardcoded Python category/term lists into a ClickHouse table + `CREATE DICTIONARY`,
queried with `dictGet` at runtime, so vocabulary grows by inserting rows instead of
redeploying code — and the agent can use the same expansion in its own SQL.

## Read first
- `apps/api/sourcecut_api/services/board.py` (`CATEGORY_TERMS`, `CATEGORY_REQUIREMENTS`)
- `tasks/018-semantic-retrieval.md` (this task covers the exact-match layer that survives 018)

## Background

Journal spelling is chaotic (Clark's spelling especially): `mocassons`, `Sah-cah-gah-weah`,
`kilt` for killed. Token search misses these without expansion. The expansion data is exactly
the shape ClickHouse dictionaries serve: small, hot, read-mostly key→values.

## Scope

### Migrations

1. `term_expansions` table — `ReplacingMergeTree(updated_at)`, `ORDER BY (category, term)`:
   `category LowCardinality(String)`, `term String`, `expansions Array(String)`,
   `notes String DEFAULT ''`, `updated_at DateTime64(3,'UTC')`.
2. `CREATE DICTIONARY sourcecut.term_expansion_dict` — `complex_key_hashed`, key
   `(category, term)`, attribute `expansions Array(String)`, `SOURCE(CLICKHOUSE(...))`
   pointing at `term_expansions`, `LIFETIME(MIN 300 MAX 600)`.
   Verify the migration runner (single statement per file) handles `CREATE DICTIONARY`; the
   dictionary source needs credentials-free self-referencing config on ClickHouse Cloud —
   confirm the `SOURCE(CLICKHOUSE(...))` form that works there and record it.

### Seeding

- Loader CLI `sourcecut-load-terms` reads `data/reference/term_expansions.json` (new,
  committed, human-editable) and upserts rows. Seed content = current `CATEGORY_TERMS` plus
  period-spelling variants gathered from the corpus (each variant must actually occur in the
  loaded corpus or in documented journal orthography — no invented terms).

### Usage

- `services/board.py`: token-layer retrieval expands each requirement term via one
  `dictGet('sourcecut.term_expansion_dict', 'expansions', (category, term))` lookup (through
  MCP `run_query`, e.g. `arrayJoin(dictGet(...))` feeding `hasTokenCaseInsensitive`), replacing
  the Python constants entirely.
- `agents/research.py`: instruction documents the dictionary and an example
  `dictGet` pattern; validator allows `dictGet` on exactly this dictionary name.
- Grants: `sourcecut_mcp_role` needs `dictGet` privilege — add to the README console block
  (`GRANT dictGet ON sourcecut.term_expansion_dict TO sourcecut_mcp_role;` — verify exact
  privilege syntax on the deployed version).

## Do not
- keep a parallel hardcoded fallback list (delete the constants; the committed JSON is the
  editable source);
- let expansion terms appear as displayed evidence — they only widen retrieval.

## Acceptance criteria

1. Bootstrap + `sourcecut-load-terms` from empty DB gives a working dictionary;
   `dictGet` returns seeded expansions (integration or preflight assertion).
2. A board build for the canonical prompt finds at least one passage reachable only via an
   expansion variant (documented example with passage id).
3. Editing the JSON, re-running the loader, and waiting past dictionary LIFETIME changes
   retrieval without any code deploy (documented manual verification).
4. `CATEGORY_TERMS` deleted from `board.py`; unit tests updated with a fake dictionary
   lookup.
5. MCP role can `dictGet`; preflight asserts it.
