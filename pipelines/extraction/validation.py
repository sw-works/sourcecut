from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

from pydantic import ValidationError

from sourcecut_api.models import (
    EvidenceValidationFailure,
    EvidenceValidationReport,
    ObservationCandidate,
    Passage,
    ValidationFailureType,
)

CandidateInput = ObservationCandidate | Mapping[str, object]


def validate_evidence(
    passage: Passage,
    candidates: Iterable[CandidateInput],
) -> EvidenceValidationReport:
    trusted: list[ObservationCandidate] = []
    failures: list[EvidenceValidationFailure] = []
    seen: set[str] = set()

    for candidate_index, raw_candidate in enumerate(candidates):
        candidate_data = _candidate_data(raw_candidate)
        try:
            candidate = ObservationCandidate.model_validate(candidate_data)
        except ValidationError as error:
            failures.append(
                _failure(
                    candidate_index,
                    "schema_validation",
                    error.json(include_url=False),
                    candidate_data,
                )
            )
            continue

        failure = _validate_candidate(passage, candidate_index, candidate, seen)
        if failure is not None:
            failures.append(failure)
            continue

        seen.add(_duplicate_key(candidate))
        trusted.append(candidate)

    return EvidenceValidationReport(
        trusted_candidates=tuple(trusted),
        failures=tuple(failures),
    )


def _validate_candidate(
    passage: Passage,
    candidate_index: int,
    candidate: ObservationCandidate,
    seen: set[str],
) -> EvidenceValidationFailure | None:
    raw_candidate = candidate.model_dump(mode="json")
    if candidate.source_end <= candidate.source_start:
        return _failure(
            candidate_index,
            "invalid_span_order",
            "source_end must be greater than source_start",
            raw_candidate,
        )
    if candidate.source_end > len(passage.passage_text):
        return _failure(
            candidate_index,
            "span_out_of_bounds",
            f"source span exceeds passage length {len(passage.passage_text)}",
            raw_candidate,
        )

    actual_quote = passage.passage_text[candidate.source_start : candidate.source_end]
    if actual_quote != candidate.source_quote:
        return _failure(
            candidate_index,
            "quote_mismatch",
            f"source span resolves to {actual_quote!r}, not {candidate.source_quote!r}",
            raw_candidate,
        )

    if _duplicate_key(candidate) in seen:
        return _failure(
            candidate_index,
            "exact_duplicate",
            "candidate exactly duplicates an earlier trusted candidate",
            raw_candidate,
        )
    return None


def _candidate_data(candidate: CandidateInput) -> dict[str, object]:
    if isinstance(candidate, ObservationCandidate):
        return candidate.model_dump(mode="json")
    return dict(candidate)


def _duplicate_key(candidate: ObservationCandidate) -> str:
    return json.dumps(
        candidate.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _failure(
    candidate_index: int,
    failure_type: ValidationFailureType,
    message: str,
    raw_candidate: dict[str, object],
) -> EvidenceValidationFailure:
    return EvidenceValidationFailure(
        candidate_index=candidate_index,
        failure_type=failure_type,
        message=message,
        raw_candidate=raw_candidate,
    )
