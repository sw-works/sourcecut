# Task 023 — Gold Fixture and Evaluation Harness

## Goal

Build the gold-observation fixture that `pipeline-spec.md` calls for and a repeatable harness
that measures the declared targets — 100% span validity, ≥95% extraction precision, ≥90%
recall — plus retrieval quality for the Task 018/019 changes. Turn "evidence-grounded" from a
claim into a number.

## Read first
- `docs/hackathon-build/pipeline-spec.md` (targets; "manually review 50–100 observations")
- `docs/hackathon-build/technical-spec.md` (evaluation targets section)
- `pipelines/extraction/validation.py`

## Background

Targets exist in two spec documents; nothing measures them. ADR-013 explicitly approves the
direct `clickhouse-connect` path for "evaluation setup". The gold fixture requires human
review by definition — the task ships the tooling and a **provisionally reviewed** fixture,
with unreviewed items clearly marked until a human pass finishes.

## Scope

### Gold fixture tooling

- `sourcecut-eval export` — pulls a deterministic sample (seeded, size configurable,
  default 100) of validated observations for the Sept 1805 window into
  `fixtures/evaluation/gold_observations_sept_1805.json` with per-item fields:
  `observation_id`, passage reference, quote, category, `verdict` (empty until reviewed),
  `reviewer`, `review_note`.
- `sourcecut-eval import` — validates reviewed verdicts (`correct|incorrect|partial`) and
  freezes the file (content hash recorded inside the file header).
- Review protocol documented in `docs/hackathon-build/evaluation-runbook.md` (new): what
  counts as correct (quote supports category+term without outside knowledge), tie-breaking,
  and the rule that fixture items are never edited — only re-verdicted.

### Recall set

Precision comes from verdicts on extracted observations; recall needs ground truth the
extractor didn't produce. Bootstrap: reviewers add `missed_observations` entries (passage id
+ quote + category) found while reading the sampled passages. Recall is measured against
sampled-passage ground truth only — state the denominator explicitly in reports.

### Harness

- `sourcecut-eval run` — offline, deterministic, no model calls:
  - **Span validity**: re-validate every stored trusted observation against stored passages
    (must be 100%; any failure lists ids).
  - **Precision/recall**: score current DB contents against the frozen fixture.
  - **Retrieval eval**: for a committed set of query→relevant-passage-id pairs
    (`fixtures/evaluation/retrieval_queries.json`, built during fixture review), report
    hit-rate@10 and MRR for (a) token-only, (b) token+dictionary, (c) hybrid with cosine —
    quantifying Tasks 014/018/19. Cosine leg requires embedded corpus; skip with a clear
    "skipped: no embeddings" marker when absent.
  - Output: JSON report to `output/eval/<timestamp>.json` + terminal summary table;
    exit nonzero if span validity < 100% or precision/recall fall below targets when the
    fixture is fully reviewed (provisional fixture → warnings, not failures).
- Extractor regression mode: `sourcecut-eval run --against <candidates.json>` scores a fresh
  extraction output file without touching the DB (for prompt/model changes before loading).

## Do not
- let the harness call Gemini (scoring is deterministic; extraction reruns are a separate
  manual step);
- auto-generate gold verdicts with a model (ADR-004 in spirit: the gold standard is human);
- write eval results into evidence tables (files under `output/`, gitignored, only).

## Acceptance criteria

1. `export → (review) → import → run` round-trips; harness runs offline in CI-able time
   (<60s) against a loaded local DB.
2. Span-validity check really catches corruption: an integration-style test mutates one
   offset in a copy and shows the failure.
3. Report shows the three retrieval legs on the committed query set with different scores
   (documented example in summary).
4. Provisional-fixture mode warns instead of failing; fully-reviewed mode enforces targets.
5. `pipeline-spec.md` and `technical-spec.md` updated to point at the runbook and harness as
   the measurement mechanism.
