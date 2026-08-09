from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pipelines.extraction.gemini import build_idempotency_key
from pipelines.extraction.validation import validate_evidence
from pipelines.journals import (
    parse_journal_entries,
    read_gutenberg_text,
    segment_entries,
    serialize_entries,
)
from sourcecut_api.db.load_gutenberg import build_source_record
from sourcecut_api.models import ExtractionResult, ObservationCandidate, SourceRecord
from sourcecut_api.repositories import ClickHouseCorpusRepository, CorpusDriftError

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "journals"
    / "gutenberg_8419_september_21_1805.txt"
)


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.insert_settings: list[dict[str, Any] | None] = []

    def query(self, query: str, parameters: dict[str, Any]) -> SimpleNamespace:
        table = next(
            table
            for table in (
                "sources",
                "journal_entries",
                "passages",
                "observations",
                "extraction_runs",
                "extraction_failures",
            )
            if f"FROM {table}" in query
        )
        records = self.tables.get(table, [])
        if table == "extraction_runs":
            matching = [
                record
                for record in records
                if record["idempotency_key"] == parameters["idempotency_key"]
            ]
            matching.sort(key=lambda record: record["started_at"], reverse=True)
            rows = [(record["run_id"], record["status"]) for record in matching[:1]]
        elif table in {"observations", "extraction_failures"}:
            id_field = "observation_id" if table == "observations" else "failure_id"
            rows = [
                (record[id_field],)
                for record in records
                if record["passage_id"] == parameters["passage_id"]
                and record[id_field] in parameters["ids"]
            ]
        else:
            fields = {
                "sources": ("source_id", "content_sha256"),
                "journal_entries": ("entry_id", "raw_text_sha256"),
                "passages": ("passage_id", "passage_sha256"),
            }[table]
            rows = [
                (record[fields[0]], record[fields[1]])
                for record in records
                if record[fields[0]] in parameters["ids"]
            ]
        return SimpleNamespace(result_rows=rows)

    def insert(
        self,
        table: str,
        data: list[list[object]],
        *,
        column_names: list[str],
        settings: dict[str, Any] | None,
    ) -> None:
        self.insert_settings.append(settings)
        self.tables.setdefault(table, []).extend(
            dict(zip(column_names, row, strict=True)) for row in data
        )


@pytest.fixture
def corpus() -> tuple[SourceRecord, tuple[Any, ...], tuple[Any, ...]]:
    entries = parse_journal_entries(read_gutenberg_text(FIXTURE))
    passages = segment_entries(entries)
    source = build_source_record(serialize_entries(entries))
    return source, entries, passages


def test_corpus_rerun_is_idempotent_and_hashes_stay_stable(
    corpus: tuple[SourceRecord, tuple[Any, ...], tuple[Any, ...]],
) -> None:
    source, entries, passages = corpus
    client = FakeClickHouseClient()
    repository = ClickHouseCorpusRepository(client)  # type: ignore[arg-type]

    first = repository.load_corpus([source], entries, passages)
    second = repository.load_corpus([source], entries, passages)

    assert first.sources_inserted == 1
    assert first.entries_inserted == len(entries)
    assert first.passages_inserted == len(passages)
    assert second.sources_inserted == 0
    assert second.entries_inserted == 0
    assert second.passages_inserted == 0
    assert len(client.tables["sources"]) == 1
    assert len(client.tables["journal_entries"]) == len(entries)
    assert len(client.tables["passages"]) == len(passages)
    assert client.tables["sources"][0]["content_sha256"] == source.content_sha256
    assert client.tables["journal_entries"][0]["raw_text_sha256"] == entries[0].raw_text_sha256
    assert client.tables["journal_entries"][0]["entry_date"] == 18050921
    assert client.tables["passages"][0]["passage_sha256"] == passages[0].passage_sha256
    assert client.tables["passages"][0]["entry_date"] == 18050921


def test_changed_source_hash_is_rejected(
    corpus: tuple[SourceRecord, tuple[Any, ...], tuple[Any, ...]],
) -> None:
    source, _, _ = corpus
    client = FakeClickHouseClient()
    repository = ClickHouseCorpusRepository(client)  # type: ignore[arg-type]
    repository.load_sources([source])
    changed = source.model_copy(update={"content_sha256": "f" * 64})

    with pytest.raises(CorpusDriftError, match="different hash"):
        repository.load_sources([changed])


def test_validated_extraction_rerun_does_not_duplicate_trusted_observations(
    corpus: tuple[SourceRecord, tuple[Any, ...], tuple[Any, ...]],
) -> None:
    _, _, passages = corpus
    passage = passages[0]
    quote = passage.passage_text[:20]
    valid = ObservationCandidate(
        category="event",
        canonical_term="journal event",
        normalized_description="The passage records an event.",
        explicit=True,
        source_quote=quote,
        source_start=0,
        source_end=len(quote),
        confidence=0.9,
    )
    invalid = valid.model_copy(update={"source_quote": "corrupted quote"})
    validation = validate_evidence(passage, [valid, invalid])
    key = build_idempotency_key(passage.passage_sha256, "model", "schema", "prompt")
    extraction = ExtractionResult(
        passage_id=passage.passage_id,
        passage_sha256=passage.passage_sha256,
        model="model",
        schema_version="schema",
        prompt_version="prompt",
        idempotency_key=key,
        candidates=(valid, invalid),
    )
    client = FakeClickHouseClient()
    repository = ClickHouseCorpusRepository(client)  # type: ignore[arg-type]

    first = repository.load_extraction(
        passage,
        extraction,
        validation,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = repository.load_extraction(passage, extraction, validation)

    assert first.skipped is False
    assert first.observations_inserted == 1
    assert first.failures_inserted == 1
    assert second.skipped is True
    assert second.run_id == first.run_id
    assert len(client.tables["observations"]) == 1
    assert client.tables["observations"][0]["trusted"] is True
    assert len(client.tables["extraction_failures"]) == 1
    assert "corrupted quote" in client.tables["extraction_failures"][0]["raw_response"]
    assert len(client.tables["extraction_runs"]) == 1


def test_small_batches_use_durable_async_inserts(
    corpus: tuple[SourceRecord, tuple[Any, ...], tuple[Any, ...]],
) -> None:
    source, entries, passages = corpus
    client = FakeClickHouseClient()

    ClickHouseCorpusRepository(client).load_corpus(  # type: ignore[arg-type]
        [source], entries, passages
    )

    assert client.insert_settings
    assert all(
        settings == {"async_insert": 1, "wait_for_async_insert": 1}
        for settings in client.insert_settings
    )


def test_source_record_hash_is_deterministic(
    corpus: tuple[SourceRecord, tuple[Any, ...], tuple[Any, ...]],
) -> None:
    source, entries, _ = corpus
    serialized = serialize_entries(entries)

    assert source == build_source_record(serialized)
    assert source.content_sha256 == hashlib.sha256(serialized).hexdigest()
