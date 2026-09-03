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

### 1 · Repository allowlist (human, once per repository) — **built**

Two tables, because they answer different questions. `licenses` says what a rights status
permits. `source_repositories` says where a repository lives and which field of its own
metadata carries a rights determination; a repository maps its vocabulary onto a license.
Collapsing them would let "we may redistribute public-domain text" stand in for "this item is
public domain", which is the substitution ADR-024 exists to prevent.

Both are committed reference data (ADR-017), so the human approval is the pull request:

- `data/reference/licenses.json`, `data/reference/source_repositories.json`
- `sourcecut-load-repositories [--check]` validates and loads them
- `sourcecut-probe-repository <id>` tests the entry's claim against the live repository

A registry entry declares `rights_field` (the dotted path stage 3 reads and nothing else) and
`eligible_values` (exact strings, compared with `==`). The loader refuses an entry with no
rights field, with a value that looks like a pattern, with a `default_license_id` no license
declares, with a non-https base URL, or with no `reviewed_by` and `reviewed_at`.

Seed set as loaded and probed on 2026-09-03:

| repository | field | probe |
|---|---|---|
| Project Gutenberg | `copyright` is `false` | 20 items, present 100%, eligible 100%, on two separate queries |
| Internet Archive | `metadata.possible-copyright-status` is `NOT_IN_COPYRIGHT` | 20 items scoped to a scanning partner's pre-1860 texts: present 100%, eligible 100%. A loose title search: 8% |
| English Wikisource | one of ten `Category:PD-*` names, matched `any_of` over `categories.title` | 25 root works, present 100%, eligible 92% |

A registry entry declares how its field is read. `rights_match: "value"` is a field holding the
determination alone; `rights_match: "any_of"` is a field holding many labels of which one may be
the determination. Both are exact string matches — `any_of` changes what the path resolves to,
not how a value is compared. Wikisource needs it because a work declares its licence by belonging
to `Category:PD-old`, next to a dozen maintenance categories.

Wikisource's two unmatched works are both correct refusals and worth keeping as the example:
`Category:EUCopyright` (reusable with conditions, not public domain) and `Category:PD-EdictGov`
(edicts of government — defensible, but it is a doctrine applied to any government's edicts
including foreign ones, so admitting it is a rights judgement nobody has made yet).

Library of Congress was probed and **rejected**. loc.gov serves no determination field for text
items: the search result carries `access_advisory` ("Open to research.", an access statement,
not a rights one) and the item endpoint carries `item.rights`, a per-collection HTML paragraph.
Prose cannot be matched with exact values, and matching it on phrases is the judgement call
ADR-024 keeps out of acquisition. This does not affect LoC media harvesting, where
`pipelines/media/loc.py` classifies rights text for assets displayed with that text beside them.

**HathiTrust** was probed and is **blocked, not rejected**. Its Bib API reports a clean
determination — `rightsCode` `pd` with `usRightsString` "Full view" — but two things stop an
entry. It has no anonymous search: `babel.hathitrust.org/cgi/ls` answers 403 and the Data API
needs credentials granted to member institutions, so discovery cannot enumerate candidates. And
rights sit per volume inside an `items[]` array of objects, which neither match mode reads.
Revisit if HathiTrust credentials are obtained; the work is a third match mode plus an
identifier-driven adapter fed from another catalogue.

**US federal works (govinfo)** were probed and carry **no rights field at all**. Package
summaries across USCOURTS and CHRG have no rights, licence or copyright key: federal works are
public domain by statute (17 USC 105), not by declaration. Admitting govinfo therefore means
accepting a categorical determination about a whole collection rather than reading a field, which
is a change to how ADR-024 decides eligibility and needs a decision, not an implementation. See
`deferred.md`.

**Adding a repository is not admitting a document.** It only makes documents proposable;
promotion at stage 5 is still the second gate. `sourcecut_mcp_role` gets no grant on
`source_repositories` — the research agent has no reason to hold a list of places to reach.

### 1a · Probe before discovery

A registry entry is a claim, not a fact: *this field carries rights, these values clear it*.
`sourcecut-probe-repository` samples real items, prints the raw value of the declared field for
each, and reports presence and match rates.

Rejection is reserved for a field that never appeared in the sample: there is then no evidence
the path exists, and every candidate would read as ineligible for a reason about the registry
rather than about the item. Both entries written from documentation failed this way on the
first run, which is the case for probing at all.

Presence below the baseline is reported as **thin**, not rejected. Several repositories record a
determination only on items a librarian reviewed, and absence there is a correct "status
unknown" that acquisition already refuses. For Internet Archive presence moves with the query
scope rather than being a property of the repository, so discovery should scope to a scanning
partner's collection and a period. A repository that matches *nothing* is still usable: holding
little public-domain material is not the same as a broken entry.

Discovery must refuse a repository that has never probed.

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

- `sourcecut_api/db/load_repositories.py` — registry validation and load. **Built.**
- `pipelines/acquisition/probe.py` — registry probe. **Built.**
- `pipelines/acquisition/` — discovery, rights determination, candidate records.
- `sourcecut_api/db/acquire.py` — fetch, register, segment, stage; `sourcecut-acquire` CLI.
- `sourcecut_api/db/promote.py` — fidelity report and promotion; `sourcecut-release` CLI
  (`report`, `promote`, `reject`).
- Migration: `candidate_sources` (candidate list with rights field and eligibility reason);
  `release_fidelity` (per-release metrics). `source_repositories` is migration 132 and is
  applied. Reuse `licenses`, `source_versions`, `raw_source_documents`, `corpus_releases`,
  `release_promotions` as they stand.
- `corpus-sources.md` gains acquired sources, written by the promotion step rather than by hand.

## Do not

- let a search result, snippet or model judgement determine rights;
- acquire from a repository with no reviewed `source_repositories` row, or from one that has
  never probed;
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
9. A registry entry with no rights field, a pattern in its eligible values, an unknown license,
   or no recorded reviewer is refused before any write. **Met.**
10. A probe reports presence and match rates separately, so a repository holding little
    public-domain material is told apart from an entry that reads the wrong field. **Met.**
