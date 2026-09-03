"""Self-consistency extraction.

A single temperature-0 extraction is one sample of the model's belief about a
passage. Sampling the same passage several times and keeping only the
observations that recur turns disagreement into a filter: a candidate that
appears in one run out of three is exactly the kind the evidence pipeline
should not trust.

Candidates are matched on the span they claim, so two runs agree only when
they point at the same words for the same reason. Span validation still runs
afterwards; this narrows what reaches it, it does not replace it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

from pipelines.extraction.gemini import build_idempotency_key
from sourcecut_api.models import ExtractionResult, ObservationCandidate, Passage
from sourcecut_api.telemetry import add_counter, telemetry_span

DEFAULT_RUNS = 3
DEFAULT_THRESHOLD = 2


class Extractor(Protocol):
    def extract(self, passage: Passage) -> ExtractionResult: ...


@dataclass(frozen=True, slots=True)
class CandidateAgreement:
    """How many independent runs produced one candidate span."""

    category: str
    canonical_term: str
    source_start: int
    source_end: int
    votes: int
    runs: int

    @property
    def ratio(self) -> float:
        return self.votes / self.runs if self.runs else 0.0


@dataclass(frozen=True, slots=True)
class ConsensusExtraction:
    result: ExtractionResult
    agreement: tuple[CandidateAgreement, ...]
    runs: int
    threshold: int
    discarded: tuple[CandidateAgreement, ...]

    @property
    def unanimous(self) -> int:
        return sum(item.votes == self.runs for item in self.agreement)


def consensus_key(candidate: ObservationCandidate) -> tuple[str, str, int, int]:
    return (
        str(candidate.category),
        candidate.canonical_term.casefold().strip(),
        candidate.source_start,
        candidate.source_end,
    )


def extract_with_self_consistency(
    extractor: Extractor,
    passage: Passage,
    *,
    runs: int = DEFAULT_RUNS,
    threshold: int = DEFAULT_THRESHOLD,
) -> ConsensusExtraction:
    """Sample one passage ``runs`` times and keep candidates seen ``threshold`` times.

    Runs are independent and go out in parallel, so wall-clock cost is one
    extraction rather than ``runs`` of them.
    """
    if runs < 1:
        raise ValueError("runs must be at least 1")
    if not 1 <= threshold <= runs:
        raise ValueError("threshold must be between 1 and runs")

    with telemetry_span(
        "sourcecut.extraction.self_consistency",
        {
            "sourcecut.passage_id": passage.passage_id,
            "sourcecut.consistency.runs": runs,
            "sourcecut.consistency.threshold": threshold,
        },
    ):
        if runs == 1:
            results = [extractor.extract(passage)]
        else:
            with ThreadPoolExecutor(max_workers=runs) as pool:
                results = list(pool.map(lambda _: extractor.extract(passage), range(runs)))

    votes: Counter[tuple[str, str, int, int]] = Counter()
    first_seen: dict[tuple[str, str, int, int], ObservationCandidate] = {}
    for result in results:
        seen_in_run: set[tuple[str, str, int, int]] = set()
        for candidate in result.candidates:
            key = consensus_key(candidate)
            if key in seen_in_run:
                # One run cannot vote twice for the same span.
                continue
            seen_in_run.add(key)
            votes[key] += 1
            first_seen.setdefault(key, candidate)

    kept: list[ObservationCandidate] = []
    agreement: list[CandidateAgreement] = []
    discarded: list[CandidateAgreement] = []
    for key, count in sorted(votes.items(), key=lambda item: (-item[1], item[0])):
        category, term, start, end = key
        record = CandidateAgreement(
            category=category,
            canonical_term=term,
            source_start=start,
            source_end=end,
            votes=count,
            runs=runs,
        )
        if count >= threshold:
            agreement.append(record)
            kept.append(first_seen[key])
        else:
            discarded.append(record)

    add_counter("sourcecut.extraction.consensus.kept", len(kept))
    add_counter("sourcecut.extraction.consensus.discarded", len(discarded))

    base = results[0]
    prompt_version = f"{base.prompt_version}+sc{runs}of{threshold}"
    result = ExtractionResult(
        passage_id=base.passage_id,
        passage_sha256=base.passage_sha256,
        model=base.model,
        schema_version=base.schema_version,
        prompt_version=prompt_version,
        idempotency_key=build_idempotency_key(
            base.passage_sha256,
            base.model,
            base.schema_version,
            prompt_version,
        ),
        candidates=tuple(kept),
    )
    return ConsensusExtraction(
        result=result,
        agreement=tuple(agreement),
        runs=runs,
        threshold=threshold,
        discarded=tuple(discarded),
    )


def agreement_summary(
    consensus: Sequence[ConsensusExtraction],
) -> dict[str, float | int]:
    """Aggregate agreement statistics across passages, for the eval report."""
    kept = sum(len(item.agreement) for item in consensus)
    discarded = sum(len(item.discarded) for item in consensus)
    unanimous = sum(item.unanimous for item in consensus)
    proposed = kept + discarded
    return {
        "passages": len(consensus),
        "candidates_proposed": proposed,
        "candidates_kept": kept,
        "candidates_discarded": discarded,
        "unanimous": unanimous,
        "kept_fraction": kept / proposed if proposed else 0.0,
        "unanimous_fraction": unanimous / kept if kept else 0.0,
    }
