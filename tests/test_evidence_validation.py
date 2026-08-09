from __future__ import annotations

import hashlib
from datetime import date

from pipelines.extraction.validation import validate_evidence
from sourcecut_api.models import Passage


def make_passage() -> Passage:
    text = "Snow fell during the night. The men could not proceed."
    return Passage(
        passage_id="test:clark:1805-09-21:1:passage:0",
        entry_id="test:clark:1805-09-21:1",
        source_id="test",
        author_id="clark",
        author_display_name="William Clark",
        entry_date=date(1805, 9, 21),
        passage_index=0,
        char_start=0,
        char_end=len(text),
        passage_text=text,
        passage_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def valid_candidate() -> dict[str, object]:
    return {
        "category": "weather",
        "canonical_term": "snow",
        "normalized_description": "Snow fell overnight.",
        "explicit": True,
        "source_quote": "Snow fell during the night.",
        "source_start": 0,
        "source_end": 27,
        "confidence": 0.98,
    }


def test_valid_candidate_is_the_only_trusted_output() -> None:
    report = validate_evidence(make_passage(), [valid_candidate()])

    assert len(report.trusted_candidates) == 1
    assert report.trusted_candidates[0].canonical_term == "snow"
    assert report.failures == ()


def test_corrupted_span_order_is_rejected_and_inspectable() -> None:
    candidate = valid_candidate() | {"source_start": 20, "source_end": 10}

    report = validate_evidence(make_passage(), [candidate])

    assert report.trusted_candidates == ()
    assert report.failures[0].failure_type == "invalid_span_order"
    assert report.failures[0].candidate_index == 0
    assert report.failures[0].raw_candidate == candidate


def test_out_of_bounds_span_is_rejected() -> None:
    candidate = valid_candidate() | {"source_end": 10_000}

    report = validate_evidence(make_passage(), [candidate])

    assert report.trusted_candidates == ()
    assert report.failures[0].failure_type == "span_out_of_bounds"


def test_corrupted_quote_is_rejected() -> None:
    candidate = valid_candidate() | {"source_quote": "Rain fell during the night."}

    report = validate_evidence(make_passage(), [candidate])

    assert report.trusted_candidates == ()
    assert report.failures[0].failure_type == "quote_mismatch"
    assert "Snow fell during the night." in report.failures[0].message


def test_invalid_category_and_confidence_are_schema_failures() -> None:
    invalid_category = valid_candidate() | {"category": "weapon"}
    invalid_confidence = valid_candidate() | {"confidence": 1.1}

    report = validate_evidence(make_passage(), [invalid_category, invalid_confidence])

    assert report.trusted_candidates == ()
    assert [failure.failure_type for failure in report.failures] == [
        "schema_validation",
        "schema_validation",
    ]
    assert report.failures[0].raw_candidate == invalid_category
    assert report.failures[1].raw_candidate == invalid_confidence


def test_exact_duplicate_is_rejected_without_hiding_first_candidate() -> None:
    candidate = valid_candidate()

    report = validate_evidence(make_passage(), [candidate, candidate])

    assert len(report.trusted_candidates) == 1
    assert len(report.failures) == 1
    assert report.failures[0].candidate_index == 1
    assert report.failures[0].failure_type == "exact_duplicate"


def test_invalid_candidate_does_not_hide_later_valid_candidate() -> None:
    invalid = valid_candidate() | {"source_quote": "corrupted"}

    report = validate_evidence(make_passage(), [invalid, valid_candidate()])

    assert len(report.trusted_candidates) == 1
    assert report.trusted_candidates[0].source_quote == "Snow fell during the night."
    assert len(report.failures) == 1
