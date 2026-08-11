# Task 025 — Additional Journal Authors

## Goal

Add at least one more expedition journalist (candidates: Sgt. John Ordway, Sgt. Patrick Gass,
Pvt. Joseph Whitehouse) from a verified public-domain, redistributable source, so
cross-author features (Tasks 020/021) compare more than two voices.

## Read first
- `docs/hackathon-build/decisions.md` (ADR-006, ADR-007 — Gutenberg-only redistribution rule)
- `pipelines/journals/gutenberg.py` (parser to generalize; heading regex is eBook-8419
  specific)
- `pipelines/journals/passages.py` (segmentation is author-agnostic already)

## Background

ADR-007 fixes the corpus rule: Project Gutenberg (or an equivalently redistributable PD
source) only; the U. Nebraska journals site is validation-only. Gass's 1807 published journal
is long-PD; Ordway/Whitehouse editions vary — the *edition* must be PD, not just the
underlying 1805 text (editorial apparatus can carry its own copyright). Rights verification
is therefore step zero and a written artifact of this task.

## Scope

### Rights + source verification (gating step)

- `docs/hackathon-build/corpus-sources.md` (new): per candidate author — the exact source
  (Gutenberg eBook id or archive.org scan), edition, editor, publication year, PD rationale,
  and a go/no-go. Only "go" sources proceed. If no Ordway/Whitehouse edition passes, Gass
  alone satisfies this task.

### Parser generalization

- `pipelines/journals/` grows per-edition parser modules behind a common interface:
  `parse(source_text) -> tuple[JournalEntry]`, each with its own `parser_version` string and
  entry-id namespace (`gutenberg-<ebook>:<author>:<date>:<ordinal>` convention preserved).
- Gass's published journal is third-person narrative with different date headings; expect a
  new heading regex + date normalization, not a tweak to the 8419 parser. The 8419 parser
  stays byte-identical in output (regression-tested).
- Author registry: `author_id` values and display names centralized (currently
  Lewis/Clark implicit); `sources` table rows per new source.

### Ingestion + downstream

- Same flow: parse → segment → extract → validate → load. Extraction prompt unchanged
  (verify it makes no Lewis/Clark assumptions; fix wording if it does — new prompt version).
- Fixture: one committed real excerpt per new author covering a date inside Sept 9–30 1805
  overlap (all candidates were on the Lolo crossing — verify per author and pick dates with
  overlap).
- Tasks 020/021 light up: entity mentions and agreement matrices must handle ≥3 authors
  without layout or query changes (grid grows a row; test it).

## Do not
- ingest from U. Nebraska or any validation-only source;
- modernize spelling (ADR-006 applies to every author);
- guess at rights — no written PD rationale, no ingestion.

## Acceptance criteria

1. `corpus-sources.md` documents rights findings for all three candidates with citations to
   the source pages.
2. ≥1 new author fully ingested: entries, passages, validated observations for the Sept 1805
   window; counts in task summary.
3. 8419 parser output byte-identical to before (serialization regression test).
4. Agreement matrix (021) renders 3+ author rows for a shared date; at least one fact
   corroborated by a new author upgrades or confirms a requirement's confidence.
5. New-author fixture tests: heading boundaries, ordinal handling, segmentation
   reconstruction — same standards as Task 002/003.
