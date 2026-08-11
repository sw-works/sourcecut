# Task 018 — Embeddings and Semantic Retrieval in ClickHouse

## Goal

Add embedding columns to `passages` and `media_assets`, backfill them with a Gemini embedding
model at ingestion time, and use brute-force `cosineDistance` ranking in ClickHouse to replace
the hardcoded keyword dictionaries and token-overlap scoring in board assembly.

## Read first
- `docs/hackathon-build/decisions.md` (ADR-004; new ADR-015 — embeddings are retrieval
  guidance, never evidence)
- `apps/api/sourcecut_api/services/board.py` (`CATEGORY_TERMS`, `CATEGORY_REQUIREMENTS`,
  `_match_score`, `STOP_WORDS`, fallback path)
- `pipelines/extraction/gemini.py` (SDK usage, idempotency pattern to copy)

## Background

Retrieval today is: hardcoded Python term lists → substring/token match → token-overlap
asset scoring. "Passages describing exhaustion" is unfindable unless a term list contains a
matching word. The corpus is small (hundreds of passages, target ≤2000 media assets), so
brute-force cosine ranking is milliseconds and needs no ANN index; the experimental
`vector_similarity` index is explicitly out of scope until scale demands it.

Evidence boundary: an embedding match may *surface* a passage; every claim shown on the board
still requires a quote-anchored trusted observation (or the labeled fallback citation). A
cosine score is never displayed as evidence and never upgrades confidence on its own.

## Scope

### Migrations

- `ALTER TABLE passages ADD COLUMN embedding Array(Float32) DEFAULT []` and
  `ADD COLUMN embedding_model LowCardinality(String) DEFAULT ''` (separate files).
- Same two for `media_assets` (embed input = title + description + subjects joined).
- If Task 016 lands first, fold columns into its rebuilds instead and skip the ALTERs —
  coordinate at implementation time; do not do both.

### Embedding backfill

- `GeminiEmbedder` integration (Google GenAI SDK, model from env
  `SOURCECUT_EMBEDDING_MODEL`, default a current `gemini-embedding` model id; dimension
  recorded; batch requests; retry policy copied from `loc.py`).
- CLI `sourcecut-embed`: scans rows where `embedding_model != <configured model>` (covers
  empty and stale), embeds in batches, writes via direct admin path. Idempotent, resumable,
  and safe to re-run; records an OTel span per batch with token/row counts.
- Ingestion loaders call the embedder inline when `SOURCECUT_EMBEDDING_ENABLED=true`, else
  rows load with empty embeddings and the CLI backfills later (keeps ingestion offline-safe
  per ADR-009).

### Retrieval changes (runtime path stays MCP `run_query`)

- Query embedding computed app-side (one Gemini call per board build per requirement group),
  then MCP `run_query` executes brute-force ranking:

  ```sql
  SELECT passage_id, entry_id, author_display_name, entry_date,
         cosineDistance(embedding, [/* floats */]) AS distance
  FROM sourcecut.passages
  WHERE entry_date BETWEEN {window} AND notEmpty(embedding)
  ORDER BY distance ASC
  LIMIT 40
  ```

- `validate_analytical_query` extended: allow `cosineDistance`/`L2Distance` and float-array
  literals; all existing rules (LIMIT, date bound, allowlist) unchanged. Array literals will
  make queries large — raise any max-query-length assumption deliberately and note the MCP
  request-size implication in the task summary.
- Board assembly becomes hybrid retrieval: candidate set = union of token match
  (`hasTokenCaseInsensitive`, Task 014) and top-K cosine; observations still filtered
  trusted-only (Task 015 policy makes this automatic on the MCP path).
- `_match_score` token-overlap asset ranking replaced by cosine between requirement text
  embedding and `media_assets.embedding`; keep the old scorer behind a flag for one release
  as a comparison fallback, delete after the eval task (023) confirms parity or better.
- `CATEGORY_TERMS` shrinks to seed terms for the token layer (full replacement is Task 019's
  dictionary).

### Config

```dotenv
SOURCECUT_EMBEDDING_ENABLED=false
SOURCECUT_EMBEDDING_MODEL=replace-with-current-embedding-model
SOURCECUT_EMBEDDING_DIMENSION=768
```

Never call the embedding API when disabled or placeholder-configured (same guard pattern as
`SOURCECUT_VIDEO_ENABLED`).

## Do not
- add a `vector_similarity`/HNSW index (out of scope; revisit at >100k rows);
- display cosine scores as evidence or let them alter confidence labels;
- embed through MCP or write through MCP;
- block ingestion on embedding availability.

## Acceptance criteria

1. `sourcecut-embed` backfills all passages + media assets; re-run is a no-op; model swap
   re-embeds only stale rows.
2. On the canonical Sept 1805 window, a semantic query for a concept absent from every term
   list (e.g. "the party is exhausted and starving") returns the known hunger/fatigue
   passages in the top 10 — asserted in an opt-in integration test with recorded ids.
3. Board build issues cosine queries through MCP `run_query` only; preflight gains a
   vector-query assertion.
4. Validator unit tests cover the new function allowance and reject mutation attempts hidden
   in array literals.
5. Unit tests use a deterministic fake embedder (hash-to-vector) — no network in the default
   suite.
6. ADR-015 recorded Final in `decisions.md`.
