# Evidence evaluation runbook

Export a deterministic 50–100 item provisional fixture with `sourcecut-eval export --size 100`.
For each item, mark `correct` only when the exact quote alone supports the category and canonical
term; mark `partial` when it supports only part, and `incorrect` otherwise. Do not use outside
knowledge. Add missed observations found while reading the sampled passages to
`missed_observations`; this sampled-passage set is the recall denominator. Set reviewer and note,
without changing evidence fields.

Run `sourcecut-eval import` only after every verdict is filled. It validates the verdict vocabulary
and records a content hash. Then run `sourcecut-eval run`. Provisional fixtures warn and report
coverage; reviewed fixtures enforce 100% spans, 95% precision, and 90% recall. Scoring never calls a
model.

Verdict weighting: only `correct` counts toward precision and recall. `partial` items are reported
as a separate `partial_fraction` and count in the recall denominator (they are real observations
the extractor only half-captured) but never in the numerator — a fixture full of half-right
extractions must not pass the gates.
