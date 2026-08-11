# Task 024 — Media Corpus Expansion (Smithsonian, NPS)

## Goal

Implement ADR-008 priorities 2 and 3 — Smithsonian Open Access (CC0) and National Park
Service — by extracting the harvester core from the LOC pipeline into shared abstractions,
and grow the cached corpus from 17 items toward the 500–2000 target in
`data-acquisition.md`.

## Read first
- `docs/hackathon-build/data-acquisition.md` (rights + historical-relationship taxonomies,
  target volumes)
- `pipelines/media/loc.py` (everything to extract: cache, allowlist, retry, rights
  classification, relationship inference)
- `docs/hackathon-build/decisions.md` (ADR-008, ADR-009)

## Scope

### Harvester core extraction

- `pipelines/media/core.py`: provider-agnostic pieces lifted from `loc.py` — write-once
  cache with `CacheConflictError`, host allowlist enforcement, content-type checks,
  429/5xx/network-only retry with the documented backoff, `MediaAsset` normalization
  helpers, thumbnail approval gating. `loc.py` refactored onto the core with **zero
  behavior change** (existing tests must pass unmodified except import paths).

### Smithsonian harvester (`pipelines/media/smithsonian.py`)

- Source: Smithsonian Open Access API (api.si.edu; API key via env
  `SMITHSONIAN_API_KEY`, ignored env file convention).
- Hard filter: CC0 only (`rights_status=PUBLIC_DOMAIN` mapping documented; anything else
  skipped and counted, never stored).
- Queries: expedition-relevant material culture and natural history (peace medals,
  espontoons, period firearms, canoes, flora/fauna types the journals name); query list in a
  committed JSON so curation is data, not code.
- Host allowlist for media: `ids.si.edu` (verify actual CDN hosts during implementation and
  pin them).

### NPS harvester (`pipelines/media/nps.py`)

- Source: NPS API (developer.nps.gov key convention as above), parks `lecl`, `nepe`, `biho`
  region assets.
- Per-item rights check exactly as ADR-008 demands: only items whose metadata states public
  domain / US-government work are stored; ambiguous → skipped and counted.
- `historical_relationship` for NPS photography is almost always `LATER_REPRESENTATION` or
  environmental `PERIOD_COMPARATIVE`; classifier extended with provider-aware rules.

### Load + integration

- Both harvesters write through `ClickHouseMediaRepository` (direct path), same idempotency
  as LOC (deterministic asset ids: `si:<id>`, `nps:<id>`).
- Embedding backfill (Task 018) covers new assets via `sourcecut-embed`.
- Board ranking at the larger corpus: verify the Task 014 token index + Task 018 cosine
  ranking keep the media query under the MCP role's execution limits at 2000 assets
  (measured, noted in summary).
- Runbook: `docs/hackathon-build/media-expansion-runbook.md` — keys, smoke commands
  (`--max-items 3`), full-harvest commands, post-load verification SQL.

### Network gating

Default test suite runs on committed fixtures (recorded API responses per provider, a few
items each). Live harvests are CLI-invoked, never in tests; ADR-009 stands — the demo runs
from cache.

## Do not
- store any non-CC0 Smithsonian or rights-ambiguous NPS item;
- hotlink external media at runtime (cache-or-absent, as today);
- let harvest failures poison the cache (write-once semantics preserved);
- change the LOC harvester's behavior while extracting the core.

## Acceptance criteria

1. LOC tests pass unmodified post-refactor (import paths aside).
2. Fixture-driven unit tests per provider: normalization, rights filtering (including a
   rejected non-CC0 fixture), relationship classification, idempotent reload.
3. A live smoke harvest (`--max-items 3` per provider) documented in the runbook and
   executed once by the implementer with counts in the task summary; full harvest to ≥500
   combined assets executed when keys/quota allow, otherwise recorded as the single open
   item (same "implemented but blocked on live acceptance" pattern as Task 013).
4. Canonical board shows at least one non-LOC asset with correct provider label and rights
   badge after a harvest + embed run.
5. Skipped-item counts (rights-filtered) reported by the CLI — silent drops forbidden.
