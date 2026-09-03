# Enhancement Plan — Tasks 014–026

Specs for the post-013 enhancement wave. Implement in numeric order; the order is
dependency-aware. Written 2026-08-11 from a full repo review.

Implementation status: Tasks 014–027 are committed. Task 023 has a provisional 71-item authentic
fixture but still requires human verdicts before precision/recall claims. Task 024 provider code,
rights gates, fixtures, and cache behavior are complete; live Smithsonian/NPS harvest acceptance
is blocked only on provider API keys/quota. Paid Veo and optional Grafana acceptance remain gated
as recorded in `deferred.md`.

## Why this wave

Review findings the wave answers:

1. ClickHouse used as a plain row store — no skip indexes, materialized views, codecs, TTLs,
   projections, dictionaries, policies, or vectors — thin for a ClickHouse partner-track
   project (ADR-001 demands centrality).
2. `research_events` migrated and tested but never written or read; session state in a
   process dict forces Cloud Run `--min 1 --max 1`; the SSE timeline is scripted.
3. Retrieval is hardcoded term lists + substring scans; the committed demo brief shows the
   keyword fallback path ran in the recorded demo.
4. Declared evaluation targets (100% span validity, ≥95% precision, ≥90% recall) are
   unmeasured; the spec'd gold fixture does not exist.
5. ADR-008 media priorities 2–3 (Smithsonian, NPS) unimplemented; 17 cached assets vs the
   500–2000 target.
6. Cross-author comparison — a stated core capability — is only term counts.

## Task map

| Task | Title | Depends on | Headline |
|---|---|---|---|
| 014 | ClickHouse physical schema | — | tokenbf indexes, `hasTokenCaseInsensitive`, passage-id projection, TTL, codecs |
| 015 | DB-enforced evidence boundary | 014 | row policy on MCP role + parametrized views (ADR-014) |
| 016 | ReplacingMergeTree idempotency | 014 | engine-native dedup, partition re-add, loader simplification |
| 017 | Durable sessions + real timeline | 016 | `research_sessions`, real `research_events`, AggregatingMergeTree rollup, kills `--max 1` (ADR-016) |
| 018 | Semantic retrieval | 016 | embeddings + brute-force `cosineDistance` through MCP (ADR-015) |
| 019 | Term-expansion dictionary | 014 | `CREATE DICTIONARY` + `dictGet`, deletes `CATEGORY_TERMS` (ADR-017) |
| 020 | Entities layer | 019 | curated registry + quote-anchored mentions, spec'd since day one |
| 021 | Cross-author agreement | 019, 020* | author×date matrix, computed corroboration → confidence |
| 022 | Map + timeline | 021 | cited route waypoints, offline SVG map, date scrubber (ADR-017) |
| 023 | Evaluation harness | 018, 019 | gold fixture + measured precision/recall/retrieval legs |
| 024 | Media expansion | 018 | Smithsonian CC0 + NPS harvesters on an extracted core |
| 025 | Additional authors | 020, 021 | rights-verified third journalist (Gass first candidate) |
| 026 | Hygiene + reconciliation | all | conftest, missing route, doc drift, deferred-decision log |
| 027 | Agentic research workflows | 017-023 | plan-then-execute, bounded coverage rounds, vocabulary memory, closed producer-critic loop, self-consistency extraction, specialist pipeline (ADR-019 to ADR-022) |

*021 works on terms alone; entity rows in the matrix need 020.

## Demo story upgrades this wave buys

- **Row-policy proof** (015): run an unfiltered `run_query` on `observations` live — the
  agent cannot see unvalidated rows even when the SQL asks for them. Engine-enforced
  invariant, strongest partner-track moment.
- **Real agent timeline** (017): the audience watches actual MCP tool calls with row counts
  stream in, instead of a scripted five-stage script.
- **Semantic find** (018): "the party is exhausted and starving" surfaces passages no
  keyword list contains, ranked by ClickHouse `cosineDistance` through the same read-only
  MCP path.
- **Three journalists on one snow day** (021/025): agreement matrix shows corroboration and
  silence, with confidence computed from it.

## Standing gates (unchanged from Tasks 001–013)

- Writes never traverse MCP; runtime reads never traverse `clickhouse-connect`.
- No historical claim without a stored, validated span (ADR-004/005); new data classes
  (reference data, embeddings, events) are explicitly non-evidence (ADR-015/016/017).
- Default test suite: offline, deterministic, no paid API calls.
- Paid/live actions (Veo run, full harvests, live MCP tests) stay env-gated with explicit
  approval markers.

## Open items carried, not created, by this wave

- Task 013 live Veo acceptance (budget approval gate).
- Native full-text index and `JSON` type — server-version checks recorded in
  `deferred.md` (Task 026).
- `vector_similarity` ANN index — deferred until corpus scale demands (ADR-015).
