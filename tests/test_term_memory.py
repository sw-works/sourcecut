from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sourcecut_api.repositories import TermExpansionRepository


class FakeTermsClient:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self.rows = rows or []
        self.inserts: list[tuple[str, list[list[Any]], list[str]]] = []

    def query(self, query: str, parameters: dict[str, Any]) -> SimpleNamespace:
        assert "term_expansions FINAL" in query
        assert parameters["category"] and parameters["term"]
        return SimpleNamespace(result_rows=self.rows)

    def insert(
        self,
        table: str,
        data: list[list[Any]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
    ) -> None:
        del settings
        self.inserts.append((table, data, column_names))


def test_new_vocabulary_is_recorded_as_discovered() -> None:
    client = FakeTermsClient()
    repository = TermExpansionRepository(client)  # type: ignore[arg-type]

    repository.record_discovered_terms("equipment", "clothing", ["Mockersons", "mockersons"])

    table, data, columns = client.inserts[0]
    assert table == "term_expansions"
    row = dict(zip(columns, data[0], strict=True))
    assert row["category"] == "equipment"
    assert row["term"] == "clothing"
    assert row["expansions"] == ["mockersons"]
    assert row["provenance"] == "discovered"


def test_curated_rows_keep_their_provenance_and_only_gain_terms() -> None:
    client = FakeTermsClient([(["clothing"], "curated", "Hand curated.")])
    repository = TermExpansionRepository(client)  # type: ignore[arg-type]

    repository.record_discovered_terms("equipment", "clothing", ["mockersons"])

    _, data, columns = client.inserts[0]
    row = dict(zip(columns, data[0], strict=True))
    assert row["expansions"] == ["clothing", "mockersons"]
    assert row["provenance"] == "curated"
    assert row["notes"] == "Hand curated."


def test_nothing_is_written_when_the_terms_are_already_known() -> None:
    client = FakeTermsClient([(["clothing", "mockersons"], "curated", "")])
    repository = TermExpansionRepository(client)  # type: ignore[arg-type]

    repository.record_discovered_terms("equipment", "clothing", ["mockersons"])

    assert client.inserts == []


def test_empty_input_is_ignored() -> None:
    client = FakeTermsClient()
    repository = TermExpansionRepository(client)  # type: ignore[arg-type]

    repository.record_discovered_terms("equipment", "clothing", ["  ", ""])
    repository.record_discovered_terms("", "clothing", ["mockersons"])

    assert client.inserts == []


def test_a_failed_memory_write_reports_why() -> None:
    """The reason is the whole value of the event.

    A missing ClickHouse grant showed on the live timeline as an unexplained red
    line, with the exception swallowed and nothing in the logs to work from.
    """
    from sourcecut_api.models import EvidenceCitation
    from sourcecut_api.models.plan import PlannedRequirement, ResearchPlan
    from sourcecut_api.services.board import ResearchBoardService

    class RefusingMemory:
        def record_discovered_terms(self, category, term, expansions):
            raise RuntimeError("Not enough privileges on sourcecut.term_expansions")

    events: list[tuple] = []
    service = ResearchBoardService(
        SimpleNamespace(call_tool=None),
        memory=RefusingMemory(),
        event_sink=lambda *event: events.append(event),
    )
    plan = ResearchPlan(
        scope_id="bitterroot-september-1805",
        title="Crossing the Bitterroots",
        window_start=18050909,
        window_end=18050930,
        rationale="Fixture plan for the memory failure path.",
        planner="static",
        prompt_version="test",
        requirements=(
            PlannedRequirement(
                category="weather",
                title="Weather",
                production_need="What the sky was doing",
                search_terms=("snow",),
                success_criteria="Two authors agree",
            ),
        ),
    )
    citation = EvidenceCitation(
        observation_id="observation:snow",
        passage_id="gutenberg:lewis:1805-09-16:passage:0",
        author_display_name="Meriwether Lewis",
        entry_date=18050916,
        category="weather",
        canonical_term="snow",
        source_quote="it snowed",
        confidence=0.9,
    )

    service._remember(plan, {"weather": ("snowing", "rained")}, (citation,))

    failure = next(event for event in events if event[0] == "memory_write_failed")
    assert "Not enough privileges" in failure[3]
    assert failure[4]["error_type"] == "RuntimeError"
