from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Protocol

from sourcecut_api.models import (
    EvidenceGroup,
    HistoricalEvidence,
    ObservationCategory,
    Passage,
)


class EvidenceRepository(Protocol):
    def search_observations(
        self,
        start_date: date,
        end_date: date,
        *,
        category: ObservationCategory | None = None,
        term: str | None = None,
        limit: int = 100,
    ) -> tuple[HistoricalEvidence, ...]: ...

    def get_passage(self, passage_id: str) -> Passage | None: ...


class HistoricalEvidenceService:
    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository

    def search_historical_evidence(
        self,
        start_date: date,
        end_date: date,
        *,
        category: ObservationCategory | None = None,
        term: str | None = None,
        limit: int = 100,
    ) -> tuple[HistoricalEvidence, ...]:
        return self._repository.search_observations(
            start_date,
            end_date,
            category=category,
            term=term,
            limit=limit,
        )

    def compare_primary_sources(
        self,
        start_date: date,
        end_date: date,
        *,
        category: ObservationCategory | None = None,
        term: str | None = None,
        limit: int = 100,
    ) -> tuple[EvidenceGroup, ...]:
        evidence = self.search_historical_evidence(
            start_date,
            end_date,
            category=category,
            term=term,
            limit=limit,
        )
        return group_by_canonical_term(evidence)

    def get_passage(self, passage_id: str) -> Passage | None:
        return self._repository.get_passage(passage_id)


def group_by_canonical_term(
    evidence: tuple[HistoricalEvidence, ...],
) -> tuple[EvidenceGroup, ...]:
    grouped: defaultdict[str, list[HistoricalEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.canonical_term].append(item)

    results: list[EvidenceGroup] = []
    for canonical_term in sorted(grouped, key=str.casefold):
        items = tuple(grouped[canonical_term])
        authors = tuple(sorted({item.author_id for item in items}))
        results.append(
            EvidenceGroup(
                canonical_term=canonical_term,
                support_level="HIGH" if len(authors) >= 2 else "SINGLE_SOURCE",
                authors=authors,
                evidence=items,
            )
        )
    return tuple(results)
