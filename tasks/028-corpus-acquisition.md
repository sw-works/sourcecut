# Task 028 — Corpus Acquisition

## Goal

Make a new period loadable without a developer writing a loader for it. Today the corpus is
whatever someone named in `corpus-sources.md` and then wrote a parser for, which is why
SourceCut answers for one expedition. Acquisition turns finding and clearing sources into a
run, and leaves the human two decisions instead of one per document.

The evidence boundary does not move. A source acquired this way is indistinguishable from
Project Gutenberg 8419 once it is loaded: same hashing, same span validation, same `trusted`
flag, same row policy.

## Read first
- `AGENTS.md`
- `docs/hackathon-build/decisions.md` (ADR-023 through ADR-025; ADR-005, ADR-007, ADR-009)
- `docs/hackathon-build/corpus-sources.md` — the existing per-source rights record
- `apps/api/sourcecut_api/db/load_gutenberg.py`, `load_gass.py` — the drift checks to match
- `apps/api/sourcecut_api/corpora/base.py` — the corpus adapter boundary

## The workflow

Five stages. Each writes to ClickHouse and can be re-run; the human appears at stages 1 and 5.

### 1 · Repository allowlist (human, once per repository)

A repository is admitted by recording its rights basis in `licenses` with `reviewed_by` and
`reviewed_at` set. Nothing is acquired from a repository that is not admitted.

Seed set: Project Gutenberg, Internet Archive (items reporting `NOT_IN_COPYRIGHT`), Library of
Congress digital collections, HathiTrust full-view, Wikisource, US federal works.

An admitted repository records which metadata field carries its rights determination, because
stage 3 reads that field and nothing else.

### 2 · Discovery (agent)

Given a period and region, search the admitted repositories for candidate source texts —
journals, letters, official reports, contemporaneous published accounts.

Perspective-guided, per ADR-023: a scene is documented by different kinds of writer, and each
suggests different searches. Enumerate two to five acquisition perspectives ("what did the
quartermaster record", "what did the missionaries record", "what did the survey parties
record"), search under each, and pool the candidates.

Output is a candidate list, not text: repository, item id, title, edition, publication year,
the rights field verbatim, and which perspective proposed it.

### 3 · Rights determination (deterministic)

For each candidate, read the rights determination from the admitted repository's declared
field. A candidate is eligible only when that field states a public-domain or otherwise
redistributable status.

The model does not decide rights, and neither does the search snippet. A candidate whose rights
field is missing, hedged, or unrecognised is recorded as ineligible with the reason, not
resolved by judgement.

### 4 · Fetch, register, segment, extract (deterministic)

For each eligible candidate:

- fetch into `raw_source_documents` with `raw_sha256`, `upstream_path`, `upstream_revision`;
- register a `license` row (the repository's, already reviewed) and a `source_version`;
- segment into `journal_entries` and `passages` through the corpus adapter;
- run extraction, producing `observations` with spans, hashes and model/prompt versions.

All of this lands in a **staged** `corpus_releases` row. Observations from a staged release are
not `trusted` and the row policy keeps them invisible to the MCP role.

### 5 · Fidelity report and promotion (human, once per release)

The staged release reports, per ADR-025:

- character-class and dictionary-hit rates per document against the loaded corpus baseline;
- structural drift — entries parsed, dates recognised, passages per entry — using the same
  checks `load_gutenberg` and `load_gass` already run;
- extraction health — span-validation failure rate, unresolvable quotes;
- the rights field verbatim for every document in the release.

A human promotes or rejects the release. `release_promotions` records `actor_id`, `action` and
`reason`. Promotion is what makes the release's observations eligible for `trusted`.

## Scope

- `pipelines/acquisition/` — discovery, rights determination, candidate records.
- `sourcecut_api/db/acquire.py` — fetch, register, segment, stage; `sourcecut-acquire` CLI.
- `sourcecut_api/db/promote.py` — fidelity report and promotion; `sourcecut-release` CLI
  (`report`, `promote`, `reject`).
- Migration: `candidate_sources` (candidate list with rights field and eligibility reason);
  `release_fidelity` (per-release metrics). Reuse `licenses`, `source_versions`,
  `raw_source_documents`, `corpus_releases`, `release_promotions` as they stand.
- `corpus-sources.md` gains acquired sources, written by the promotion step rather than by hand.

## Do not

- let a search result, snippet or model judgement determine rights;
- acquire from a repository with no reviewed `licenses` row;
- mark an observation `trusted` before its release is promoted;
- repair, modernise or re-OCR acquired text — the gate rejects unusable text, it does not fix it
  (ADR-006);
- let acquisition reach the runtime path: no web access from the research agent, ever (ADR-023);
- make the default test suite require network access.

## Acceptance criteria

1. Discovery against an admitted repository returns candidates carrying the rights field
   verbatim and the perspective that proposed each.
2. A candidate from an unadmitted repository is refused before any fetch.
3. A candidate whose rights field is missing or unrecognised is recorded ineligible with the
   reason, and is never fetched.
4. An acquired document lands in `raw_source_documents` with a hash and upstream revision, and
   its passages carry the same span guarantees as Gutenberg 8419.
5. Observations in a staged release are invisible to the MCP role and cannot be `trusted`.
6. A release whose OCR fidelity or structural drift is below baseline fails the report and
   cannot be promoted.
7. Promotion records the actor and reason, and only then may the release's observations be
   validated and marked trusted.
8. The whole path runs with no Gemini credential for everything except extraction.
