# Task 029 — Terra Nova as a second research corpus

## Goal

Prove the research workflow is not Lewis-and-Clark-shaped by running it, unchanged,
over a second corpus: Scott's Terra Nova expedition, 1910–1912.

## Read first
- `pipelines/journals/gutenberg.py` and `pipelines/journals/gass.py` — the two existing
  parsers; a third follows their shape
- `data/reference/research_scopes.json` — the windows a plan may choose
- `docs/hackathon-build/decisions.md` ADR-004, ADR-013 (evidence provenance)

## Sources

| Source | Author | Text | Shape |
|---|---|---|---|
| `gutenberg-11579` | Robert Falcon Scott | *Scott's Last Expedition*, Vol. I | **378 dated entries**, `_Saturday, May_ 27.--` |

Project Gutenberg public domain, the same provenance as the Lewis and Clark corpus.

### What the survey found, 2026-09-06

Scott is the only sustained dated diary of this expedition in the public domain and in
machine-readable form. Measured, not assumed:

- **Amundsen**, *The South Pole* Vol. II (`gutenberg-3415`): a narrative, not a diary —
  **9** dated headings in the whole volume.
- **Cherry-Garrard**, *The Worst Journey in the World* (`gutenberg-14363`): quotes Bowers
  and Wilson at length, but embedded inside his own narration. Attribution inside a
  quotation is not attribution by a heading (see **Do not**).
- **Taylor**, *With Scott: The Silver Lining* (1916, archive.org): narrative, and the OCR
  is poor — 3 date-shaped lines in 980 KB.
- Wilson's and Bowers's own diaries were first published in 1966 and 1972 and are in
  copyright.

**So this corpus is single-source.** Every requirement it answers is corroborated by one
man, and the board must say so rather than showing a one-row agreement matrix as though
it were the three-diarist kind. That is the price of the corpus, and it is worth paying
only if the product states it plainly.

## Scope

### Parsing

- `pipelines/journals/terra_nova.py`: one parser per source, following the existing
  protocol (`JournalParser`).
- Neither text repeats the year on an entry. Scott gives a weekday, so the year is
  **resolved** from weekday + month + day against the expedition's years and fails loudly
  when no year fits — a parse that cannot place a date must not guess one. Amundsen gives
  a weekday only sometimes; unweekdayed entries take the year from the running cursor and
  roll over when the month goes backwards.
- Authors are added to `pipelines/journals/authors.py`.

### Windows

- Scope entries for the segments a production would ask about: the winter at Cape Evans,
  the depot journey, the race south, the return march.
- A scope names its corpus, so a brief about the Bitterroots cannot select an Antarctic
  window and vice versa.

### Corroboration, and its absence

The Lewis and Clark corpus corroborates a claim across three men in the same party on the
same day. Terra Nova cannot: it has one diarist. Scopes for this corpus carry
`minimum_authors: 1`, and the board says "one diarist, no corroboration available in this
corpus" — never `single_source` styled as a near-miss, which reads as a shortfall in the
search rather than a fact about the record.

## Do not
- infer a date the text does not support;
- parse quoted diary extracts embedded in someone else's narrative (Cherry-Garrard
  quotes Bowers and Wilson at length) — attribution inside a quotation is not the same
  as attribution by a heading, and this system's whole value is exact spans;
- present cross-party corroboration in the same words as same-party corroboration.

## Acceptance criteria

1. Both parsers produce dated entries with exact character spans, and a text the parser
   cannot place raises rather than defaults.
2. A brief about the polar journey selects an Antarctic window and returns Scott's
   evidence with exact spans.
3. A brief about the Bitterroots still selects a Lewis and Clark window.
4. The board states that this corpus has one diarist, in its own words, wherever the
   Lewis and Clark board would show corroboration.
