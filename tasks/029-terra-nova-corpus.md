# Task 029 — Terra Nova as a second research corpus

## Goal

Prove the research workflow is not Lewis-and-Clark-shaped by running it, unchanged,
over a second corpus: the race to the South Pole, 1910–1912. Two parties kept dated
journals through the same weeks, both are public domain, and both are machine-readable.

## Read first
- `pipelines/journals/gutenberg.py` and `pipelines/journals/gass.py` — the two existing
  parsers; a third follows their shape
- `data/reference/research_scopes.json` — the windows a plan may choose
- `docs/hackathon-build/decisions.md` ADR-004, ADR-013 (evidence provenance)

## Sources

| Source | Author | Text | Shape |
|---|---|---|---|
| `gutenberg-11579` | Robert Falcon Scott | *Scott's Last Expedition*, Vol. I | 378 dated entries, `_Saturday, May_ 27.--` |
| `gutenberg-3415` | Roald Amundsen | *The South Pole*, Vol. II | dated entries through the polar journey, `Monday, December 4. -- ` |

Both are Project Gutenberg public-domain texts, the same provenance as the Lewis and
Clark corpus.

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

### What "two authors" means here

The Lewis and Clark corpus corroborates a claim across three men who were in the same
party on the same day. Terra Nova corroborates across two **parties** who were on the
same continent in the same week. That is a weaker claim and the board must say so rather
than reusing a label that means something else.

## Do not
- infer a date the text does not support;
- parse quoted diary extracts embedded in someone else's narrative (Cherry-Garrard
  quotes Bowers and Wilson at length) — attribution inside a quotation is not the same
  as attribution by a heading, and this system's whole value is exact spans;
- present cross-party corroboration in the same words as same-party corroboration.

## Acceptance criteria

1. Both parsers produce dated entries with exact character spans, and a text the parser
   cannot place raises rather than defaults.
2. A brief about the polar journey selects an Antarctic window and returns evidence from
   both parties.
3. A brief about the Bitterroots still selects a Lewis and Clark window.
4. The board labels cross-party corroboration in its own words.
