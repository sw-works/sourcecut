# Task 021 — Cross-Author Agreement View

## Goal

Surface corroboration: for each board requirement (and optionally entity), show per-author,
per-date presence so a filmmaker sees "Clark reports snow Sept 16; Lewis's entry that day is
silent" — and let multi-author corroboration feed the existing confidence taxonomy.

## Read first
- `docs/hackathon-build/product-plan.md` (confidence taxonomy HIGH/MEDIUM/INTERPRETIVE/UNSUPPORTED)
- `apps/api/sourcecut_api/services/board.py` (`verify_asset`, requirement assembly)
- `tasks/020-entities-layer.md`

## Background

The demo query already counts terms per author; nothing turns that into a visible
agreement/silence matrix or into confidence. Silence is not disagreement — an author with no
entry that day is different from an author whose entry omits the term. The matrix must
distinguish three cell states: `mentions`, `entry-without-mention`, `no-entry`.

## Scope

### Query (runtime through MCP)

- Parametrized view `author_date_matrix(term String, start Int32, end Int32)`:
  per `(author_id, entry_date)` — entry exists (from `journal_entries`), token/expansion hit
  count (from `passages`, using the Task 019 dictionary), and trusted observation count for
  the term (from `observations`). One view, three source tables, `FINAL` as needed.

### Service + API

- `AgreementService.build_matrix(term, window)` → typed rows with the three-state cells and a
  `corroboration` summary: number of distinct authors with trusted evidence for the term in
  the window.
- Board integration: requirement confidence upgrades to HIGH only when corroboration ≥ 2
  authors (today's rule-of-thumb becomes explicit and computed); single-author evidence
  labels SINGLE_SOURCE exactly as the existing taxonomy defines. No downgrades below current
  behavior without a documented reason.
- API: matrix embedded in the board payload per requirement (avoid a chatty per-term
  endpoint; the board build already knows its terms).

### UI

- Evidence Matrix section gains a per-requirement expandable author×date grid: rows =
  authors, columns = dates in window, cells colored/labeled by the three states, cell click
  opens the passage(s) in the existing inspector.
- Corroboration badge on each requirement ("2 authors, 5 days").
- Accessible: grid navigable by keyboard, states not color-only.

## Do not
- infer disagreement/conflict semantics (an author omitting a term is silence, never
  contradiction — copy states this explicitly);
- issue one MCP query per cell (one view call per requirement, shaped in SQL);
- alter the UNSUPPORTED path.

## Acceptance criteria

1. Canonical prompt: at least one requirement shows a matrix with all three cell states
   present across the Sept 1805 window, matching hand-checked journal facts for two dates
   (documented in the task summary with passage ids).
2. A requirement backed by two authors displays HIGH with the corroboration badge; a
   single-author requirement displays SINGLE_SOURCE. Unit-tested via fake MCP rows.
3. Cell click resolves to exact passages through the existing deterministic lookup.
4. Board JSON schema change is versioned and the frontend handles boards without matrices
   (older stored sessions from Task 017) gracefully.
5. Keyboard + screen-reader pass on the grid (axe or manual notes in summary).
