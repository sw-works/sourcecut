from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pipelines.journals import parse_journal_entries, read_gutenberg_text, segment_entries
from sourcecut_api.repositories.evidence import ClickHouseEvidenceRepository
from sourcecut_api.services import HistoricalEvidenceService

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "journals"
    / "gutenberg_8419_september_21_1805.txt"
)


class FakeEvidenceClient:
    def __init__(
        self,
        evidence_rows: list[tuple[object, ...]],
        passage_row: tuple[object, ...],
    ) -> None:
        self.evidence_rows = evidence_rows
        self.passage_row = passage_row
        self.calls: list[tuple[str, dict[str, object], dict[str, object]]] = []

    def query(
        self,
        query: str,
        *,
        parameters: dict[str, object],
        settings: dict[str, object],
    ) -> SimpleNamespace:
        self.calls.append((query, parameters, settings))
        rows = self.evidence_rows if "ALL INNER JOIN" in query else [self.passage_row]
        return SimpleNamespace(result_rows=rows)


def make_client() -> tuple[FakeEvidenceClient, Any, Any]:
    entries = parse_journal_entries(read_gutenberg_text(FIXTURE))
    passages = segment_entries(entries)
    lewis = passages[0]
    clark = passages[1]
    evidence_rows = []
    for index, (passage, quote) in enumerate(
        (
            (lewis, "food for our horses"),
            (clark, "horse load of roots"),
        ),
        start=1,
    ):
        source_start = passage.passage_text.index(quote)
        evidence_rows.append(
            (
                f"observation-{index}",
                passage.passage_id,
                passage.entry_id,
                passage.source_id,
                passage.author_id,
                passage.author_display_name,
                18050921,
                "animal",
                "horse",
                "The passage explicitly mentions a horse or horses.",
                True,
                quote,
                source_start,
                source_start + len(quote),
                passage.passage_sha256.encode("ascii"),
                0.95,
                passage.passage_text,
            )
        )
    passage_row = (
        lewis.passage_id,
        lewis.entry_id,
        lewis.source_id,
        lewis.author_id,
        lewis.author_display_name,
        18050921,
        lewis.passage_index,
        lewis.char_start,
        lewis.char_end,
        lewis.passage_text,
        lewis.passage_sha256.encode("ascii"),
    )
    return FakeEvidenceClient(evidence_rows, passage_row), lewis, clark


def test_september_evidence_groups_across_lewis_and_clark() -> None:
    client, lewis, clark = make_client()
    repository = ClickHouseEvidenceRepository(client)  # type: ignore[arg-type]
    service = HistoricalEvidenceService(repository)

    groups = service.compare_primary_sources(
        date(1805, 9, 9),
        date(1805, 9, 30),
        category="animal",
        term="horse",
    )

    assert len(groups) == 1
    assert groups[0].canonical_term == "horse"
    assert groups[0].support_level == "HIGH"
    assert set(groups[0].authors) == {"lewis", "clark"}
    assert {item.passage_id for item in groups[0].evidence} == {
        lewis.passage_id,
        clark.passage_id,
    }
    assert all(item.source_quote in item.passage_text for item in groups[0].evidence)


def test_repository_uses_fixed_parameterized_valid_only_query() -> None:
    client, _, _ = make_client()
    repository = ClickHouseEvidenceRepository(client)  # type: ignore[arg-type]
    hostile_term = "pine'); DROP TABLE observations; --"

    repository.search_observations(
        date(1805, 9, 9),
        date(1805, 9, 30),
        category="terrain",
        term=hostile_term,
        limit=25,
    )

    query, parameters, settings = client.calls[0]
    assert hostile_term not in query
    # The hostile term is tokenized before binding; only bare alphanumeric
    # tokens reach ClickHouse, each as its own bound parameter.
    assert parameters == {
        "start_date": 18050909,
        "end_date": 18050930,
        "limit": 25,
        "category": "terrain",
        "term_0": "pine",
        "term_1": "drop",
        "term_2": "table",
        "term_3": "observations",
    }
    assert "trusted = true" in query
    assert "validation_status = 'valid'" in query
    assert "hasToken(lower(canonical_term)" in query
    assert "positionCaseInsensitiveUTF8" not in query
    assert "ALL INNER JOIN" in query
    assert query.count(" FINAL") == 2
    assert settings["max_execution_time"] == 30
    assert settings["max_rows_to_read"] == 1_000_000


def test_passage_lookup_returns_exact_stored_passage() -> None:
    client, expected, _ = make_client()
    service = HistoricalEvidenceService(
        ClickHouseEvidenceRepository(client)  # type: ignore[arg-type]
    )

    passage = service.get_passage(expected.passage_id)

    assert passage == expected
    query, parameters, _ = client.calls[0]
    assert expected.passage_id not in query
    assert parameters == {"passage_id": expected.passage_id}
    assert "LIMIT 2" in query
    assert "FROM passages FINAL" in query


def test_search_rejects_invalid_range_and_limit() -> None:
    client, _, _ = make_client()
    repository = ClickHouseEvidenceRepository(client)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="end_date"):
        repository.search_observations(date(1805, 9, 30), date(1805, 9, 9))
    with pytest.raises(ValueError, match="limit"):
        repository.search_observations(date(1805, 9, 9), date(1805, 9, 30), limit=0)
    assert client.calls == []


def test_multi_word_term_is_tokenized_for_has_token() -> None:
    client = FakeEvidenceClient([], ())
    repository = ClickHouseEvidenceRepository(client)  # type: ignore[arg-type]

    repository.search_observations(
        date(1805, 9, 9), date(1805, 9, 30), term="pack horse"
    )

    query, parameters, _ = client.calls[-1]
    assert "{term_0:String}" in query and "{term_1:String}" in query
    assert parameters["term_0"] == "pack" and parameters["term_1"] == "horse"
