from __future__ import annotations

import hashlib
import threading
from collections.abc import Sequence

import pytest

from pipelines.extraction import (
    agreement_summary,
    extract_with_self_consistency,
)
from sourcecut_api.models import ExtractionResult, ObservationCandidate, Passage

PASSAGE_TEXT = (
    "we passed over a mountain covered with snow and the horses suffered much "
    "for want of food"
)


def passage() -> Passage:
    return Passage(
        passage_id="gutenberg-8419:clark:1805-09-16:passage:0",
        entry_id="gutenberg-8419:clark:1805-09-16:1",
        source_id="gutenberg-8419",
        author_id="clark",
        author_display_name="William Clark",
        entry_date="1805-09-16",
        passage_index=0,
        char_start=0,
        char_end=len(PASSAGE_TEXT),
        passage_text=PASSAGE_TEXT,
        passage_sha256=hashlib.sha256(PASSAGE_TEXT.encode()).hexdigest(),
    )


def candidate(
    category: str, term: str, quote: str, *, description: str = "Observed detail."
) -> ObservationCandidate:
    start = PASSAGE_TEXT.index(quote)
    return ObservationCandidate(
        category=category,
        canonical_term=term,
        normalized_description=description,
        explicit=True,
        source_quote=quote,
        source_start=start,
        source_end=start + len(quote),
        confidence=0.9,
    )


class ScriptedExtractor:
    """Returns one scripted candidate set per call, in order.

    Runs are dispatched in parallel, so handing out the next script has to be
    atomic or the test flakes.
    """

    def __init__(self, runs: Sequence[Sequence[ObservationCandidate]]) -> None:
        self._runs = list(runs)
        self._lock = threading.Lock()
        self.calls = 0

    def extract(self, target: Passage) -> ExtractionResult:
        with self._lock:
            index = min(self.calls, len(self._runs) - 1)
            self.calls += 1
        candidates = self._runs[index]
        return ExtractionResult(
            passage_id=target.passage_id,
            passage_sha256=target.passage_sha256,
            model="gemini-test",
            schema_version="observation-candidate-v1",
            prompt_version="primary-source-extraction-v2",
            idempotency_key="0" * 64,
            candidates=tuple(candidates),
        )


def test_candidates_below_the_vote_threshold_are_discarded() -> None:
    snow = candidate("weather", "snow", "snow")
    horses = candidate("transportation", "horses", "the horses suffered much")
    invented = candidate("event", "council", "passed over a mountain")
    extractor = ScriptedExtractor(
        [
            (snow, horses, invented),
            (snow, horses),
            (snow, horses),
        ]
    )

    consensus = extract_with_self_consistency(extractor, passage(), runs=3, threshold=2)

    assert extractor.calls == 3
    kept = {item.canonical_term for item in consensus.result.candidates}
    assert kept == {"snow", "horses"}
    assert [item.canonical_term for item in consensus.discarded] == ["council"]
    assert consensus.unanimous == 2


def test_same_term_at_a_different_span_is_a_separate_claim() -> None:
    early = candidate("weather", "snow", "snow")
    late = candidate("weather", "snow", "covered with snow")
    extractor = ScriptedExtractor([(early,), (late,), (early,)])

    consensus = extract_with_self_consistency(extractor, passage(), runs=3, threshold=2)

    spans = {
        (item.source_start, item.source_end) for item in consensus.result.candidates
    }
    assert spans == {(early.source_start, early.source_end)}
    assert [item.votes for item in consensus.discarded] == [1]


def test_repeated_span_inside_one_run_votes_once() -> None:
    snow = candidate("weather", "snow", "snow")
    extractor = ScriptedExtractor([(snow, snow), (snow, snow), ()])

    consensus = extract_with_self_consistency(extractor, passage(), runs=3, threshold=3)

    assert consensus.result.candidates == ()
    assert consensus.discarded[0].votes == 2


def test_consensus_prompt_version_and_key_differ_from_single_shot() -> None:
    snow = candidate("weather", "snow", "snow")
    extractor = ScriptedExtractor([(snow,)])
    single = extractor.extract(passage())

    consensus = extract_with_self_consistency(extractor, passage(), runs=2, threshold=1)

    assert consensus.result.prompt_version == "primary-source-extraction-v2+sc2of1"
    assert consensus.result.idempotency_key != single.idempotency_key


def test_agreement_summary_counts_across_passages() -> None:
    snow = candidate("weather", "snow", "snow")
    stray = candidate("event", "council", "passed over a mountain")
    consensus = [
        extract_with_self_consistency(
            ScriptedExtractor([(snow, stray), (snow,)]), passage(), runs=2, threshold=2
        )
    ]

    summary = agreement_summary(consensus)

    assert summary["candidates_proposed"] == 2
    assert summary["candidates_kept"] == 1
    assert summary["candidates_discarded"] == 1
    assert summary["unanimous"] == 1


def test_invalid_threshold_is_rejected() -> None:
    extractor = ScriptedExtractor([()])
    with pytest.raises(ValueError, match="threshold"):
        extract_with_self_consistency(extractor, passage(), runs=2, threshold=3)
