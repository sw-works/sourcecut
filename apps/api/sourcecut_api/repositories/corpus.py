from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sourcecut_api.models import (
    EvidenceValidationFailure,
    EvidenceValidationReport,
    ExtractionResult,
    JournalEntry,
    ObservationCandidate,
    Passage,
    SourceRecord,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

BATCH_SIZE = 10_000
ASYNC_INSERT_THRESHOLD = 1_000
ASYNC_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}


class CorpusDriftError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CorpusLoadResult:
    sources_inserted: int
    entries_inserted: int
    passages_inserted: int


@dataclass(frozen=True, slots=True)
class ExtractionLoadResult:
    run_id: str
    skipped: bool
    observations_inserted: int
    failures_inserted: int


class ClickHouseCorpusRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load_corpus(
        self,
        sources: Sequence[SourceRecord],
        entries: Sequence[JournalEntry],
        passages: Sequence[Passage],
    ) -> CorpusLoadResult:
        return CorpusLoadResult(
            sources_inserted=self.load_sources(sources),
            entries_inserted=self.load_entries(entries),
            passages_inserted=self.load_passages(passages),
        )

    def load_sources(self, sources: Sequence[SourceRecord]) -> int:
        unique = _unique_by_id(sources, "source_id", "content_sha256")
        missing = self._missing_by_hash(
            "sources",
            "source_id",
            "content_sha256",
            unique,
        )
        rows = [
            [
                source.source_id,
                source.provider,
                source.title,
                source.source_url,
                source.edition_notes,
                source.rights_status,
                source.raw_metadata,
                source.content_sha256,
            ]
            for source in missing
        ]
        return self._insert_rows(
            "sources",
            [
                "source_id",
                "provider",
                "title",
                "source_url",
                "edition_notes",
                "rights_status",
                "raw_metadata",
                "content_sha256",
            ],
            rows,
        )

    def load_entries(self, entries: Sequence[JournalEntry]) -> int:
        unique = _unique_by_id(entries, "entry_id", "raw_text_sha256")
        missing = self._missing_by_hash(
            "journal_entries",
            "entry_id",
            "raw_text_sha256",
            unique,
            date_field="entry_date",
        )
        rows = [
            [
                entry.entry_id,
                entry.source_id,
                entry.author_id,
                entry.author_display_name,
                _calendar_date_key(entry.entry_date),
                entry.ordinal_for_day,
                entry.heading,
                entry.raw_text,
                entry.source_url,
                entry.source_locator,
                entry.raw_text_sha256,
                entry.parser_version,
            ]
            for entry in missing
        ]
        return self._insert_rows(
            "journal_entries",
            [
                "entry_id",
                "source_id",
                "author_id",
                "author_display_name",
                "entry_date",
                "ordinal_for_day",
                "heading",
                "raw_text",
                "source_url",
                "source_locator",
                "raw_text_sha256",
                "parser_version",
            ],
            rows,
        )

    def load_passages(self, passages: Sequence[Passage]) -> int:
        unique = _unique_by_id(passages, "passage_id", "passage_sha256")
        missing = self._missing_by_hash(
            "passages",
            "passage_id",
            "passage_sha256",
            unique,
            date_field="entry_date",
        )
        rows = [
            [
                passage.passage_id,
                passage.entry_id,
                passage.source_id,
                passage.author_id,
                passage.author_display_name,
                _calendar_date_key(passage.entry_date),
                passage.passage_index,
                passage.char_start,
                passage.char_end,
                passage.passage_text,
                passage.passage_sha256,
            ]
            for passage in missing
        ]
        return self._insert_rows(
            "passages",
            [
                "passage_id",
                "entry_id",
                "source_id",
                "author_id",
                "author_display_name",
                "entry_date",
                "passage_index",
                "char_start",
                "char_end",
                "passage_text",
                "passage_sha256",
            ],
            rows,
        )

    def load_extraction(
        self,
        passage: Passage,
        extraction: ExtractionResult,
        validation: EvidenceValidationReport,
        *,
        attempt: int = 1,
        started_at: datetime | None = None,
    ) -> ExtractionLoadResult:
        if extraction.passage_id != passage.passage_id:
            raise ValueError("Extraction passage_id does not match passage")
        if extraction.passage_sha256 != passage.passage_sha256:
            raise CorpusDriftError("Extraction passage hash does not match passage")
        if not 1 <= attempt <= 255:
            raise ValueError("attempt must fit ClickHouse UInt8")

        existing = self._client.query(
            "SELECT run_id, status FROM extraction_runs "
            "WHERE idempotency_key = {idempotency_key:String} "
            "ORDER BY started_at DESC LIMIT 1",
            parameters={"idempotency_key": extraction.idempotency_key},
        ).result_rows
        if existing and str(existing[0][1]) == "completed":
            return ExtractionLoadResult(
                run_id=str(existing[0][0]),
                skipped=True,
                observations_inserted=0,
                failures_inserted=0,
            )

        run_id = _stable_id("run", extraction.idempotency_key)
        observations_inserted = self._insert_observations(
            run_id,
            passage,
            extraction,
            validation.trusted_candidates,
        )
        failures_inserted = self._insert_failures(
            run_id,
            passage,
            validation.failures,
            attempt,
        )
        start = started_at or datetime.now(UTC)
        self._insert_rows(
            "extraction_runs",
            [
                "run_id",
                "idempotency_key",
                "passage_id",
                "passage_sha256",
                "model",
                "schema_version",
                "prompt_version",
                "status",
                "attempt",
                "observations_inserted",
                "started_at",
                "completed_at",
                "error_message",
            ],
            [[
                run_id,
                extraction.idempotency_key,
                passage.passage_id,
                passage.passage_sha256,
                extraction.model,
                extraction.schema_version,
                extraction.prompt_version,
                "completed",
                attempt,
                len(validation.trusted_candidates),
                start,
                datetime.now(UTC),
                "",
            ]],
        )
        return ExtractionLoadResult(
            run_id=run_id,
            skipped=False,
            observations_inserted=observations_inserted,
            failures_inserted=failures_inserted,
        )

    def _insert_observations(
        self,
        run_id: str,
        passage: Passage,
        extraction: ExtractionResult,
        candidates: Sequence[ObservationCandidate],
    ) -> int:
        records = [
            (_observation_id(passage, extraction, candidate), candidate)
            for candidate in candidates
        ]
        existing_ids = self._existing_ids(
            "observations",
            "observation_id",
            [record_id for record_id, _ in records],
            passage_id=passage.passage_id,
        )
        rows = [
            [
                observation_id,
                run_id,
                passage.passage_id,
                passage.entry_id,
                passage.source_id,
                candidate.category,
                candidate.canonical_term,
                candidate.normalized_description,
                candidate.explicit,
                candidate.source_quote,
                candidate.source_start,
                candidate.source_end,
                passage.passage_sha256,
                candidate.confidence,
                extraction.model,
                extraction.schema_version,
                extraction.prompt_version,
                True,
                "valid",
            ]
            for observation_id, candidate in records
            if observation_id not in existing_ids
        ]
        return self._insert_rows(
            "observations",
            [
                "observation_id",
                "extraction_run_id",
                "passage_id",
                "entry_id",
                "source_id",
                "category",
                "canonical_term",
                "normalized_description",
                "explicit",
                "source_quote",
                "source_start",
                "source_end",
                "passage_sha256",
                "confidence",
                "model",
                "schema_version",
                "prompt_version",
                "trusted",
                "validation_status",
            ],
            rows,
        )

    def _insert_failures(
        self,
        run_id: str,
        passage: Passage,
        failures: Sequence[EvidenceValidationFailure],
        attempt: int,
    ) -> int:
        records = [(_failure_id(run_id, failure), failure) for failure in failures]
        existing_ids = self._existing_ids(
            "extraction_failures",
            "failure_id",
            [record_id for record_id, _ in records],
            passage_id=passage.passage_id,
        )
        rows = [
            [
                failure_id,
                run_id,
                passage.passage_id,
                failure.failure_type,
                False,
                attempt,
                failure.message,
                json.dumps(
                    failure.raw_candidate,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ]
            for failure_id, failure in records
            if failure_id not in existing_ids
        ]
        return self._insert_rows(
            "extraction_failures",
            [
                "failure_id",
                "run_id",
                "passage_id",
                "failure_type",
                "retryable",
                "attempt",
                "error_message",
                "raw_response",
            ],
            rows,
        )

    def _missing_by_hash(
        self,
        table: str,
        id_field: str,
        hash_field: str,
        records: Sequence[Any],
        *,
        date_field: str | None = None,
    ) -> list[Any]:
        if not records:
            return []
        existing: dict[str, set[str]] = {}
        for batch in _chunks(records):
            parameters: dict[str, object] = {"ids": [getattr(record, id_field) for record in batch]}
            date_clause = ""
            if date_field is not None:
                dates = [_calendar_date_key(getattr(record, date_field)) for record in batch]
                parameters.update({"date_start": min(dates), "date_end": max(dates)})
                date_clause = (
                    f"{date_field} BETWEEN {{date_start:Int32}} AND {{date_end:Int32}} AND "
                )
            rows = self._client.query(
                f"SELECT {id_field}, {hash_field} FROM {table} WHERE "
                f"{date_clause}{id_field} IN {{ids:Array(String)}}",
                parameters=parameters,
            ).result_rows
            for record_id, content_hash in rows:
                existing.setdefault(str(record_id), set()).add(_hash_text(content_hash))

        missing: list[Any] = []
        for record in records:
            record_id = str(getattr(record, id_field))
            expected_hash = str(getattr(record, hash_field))
            hashes = existing.get(record_id)
            if hashes is None:
                missing.append(record)
            elif hashes != {expected_hash}:
                raise CorpusDriftError(f"{table}.{record_id} exists with a different hash")
        return missing

    def _existing_ids(
        self,
        table: str,
        id_field: str,
        ids: Sequence[str],
        *,
        passage_id: str,
    ) -> set[str]:
        if not ids:
            return set()
        rows = self._client.query(
            f"SELECT {id_field} FROM {table} "
            f"WHERE passage_id = {{passage_id:String}} AND {id_field} IN {{ids:Array(String)}}",
            parameters={"passage_id": passage_id, "ids": list(ids)},
        ).result_rows
        return {str(row[0]) for row in rows}

    def _insert_rows(
        self,
        table: str,
        column_names: Sequence[str],
        rows: Sequence[Sequence[object]],
    ) -> int:
        inserted = 0
        for batch in _chunks(rows):
            settings = ASYNC_INSERT_SETTINGS if len(batch) < ASYNC_INSERT_THRESHOLD else None
            self._client.insert(
                table,
                list(batch),
                column_names=list(column_names),
                settings=settings,
            )
            inserted += len(batch)
        return inserted


def _unique_by_id(records: Sequence[Any], id_field: str, hash_field: str) -> list[Any]:
    unique: dict[str, Any] = {}
    for record in records:
        record_id = str(getattr(record, id_field))
        previous = unique.get(record_id)
        if previous is not None and getattr(previous, hash_field) != getattr(record, hash_field):
            raise CorpusDriftError(f"Input contains conflicting hashes for {record_id}")
        unique[record_id] = record
    return list(unique.values())


def _chunks(values: Sequence[Any]) -> list[Sequence[Any]]:
    return [values[index : index + BATCH_SIZE] for index in range(0, len(values), BATCH_SIZE)]


def _hash_text(value: str | bytes) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else value


def _calendar_date_key(value: Any) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def _stable_id(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(f"{prefix}\0{payload}".encode()).hexdigest()
    return f"{prefix}:{digest}"


def _observation_id(
    passage: Passage,
    extraction: ExtractionResult,
    candidate: ObservationCandidate,
) -> str:
    payload = json.dumps(
        [
            passage.passage_id,
            extraction.model,
            extraction.schema_version,
            extraction.prompt_version,
            candidate.model_dump(mode="json"),
        ],
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _stable_id("observation", payload)


def _failure_id(run_id: str, failure: EvidenceValidationFailure) -> str:
    payload = json.dumps(
        [run_id, failure.model_dump(mode="json")],
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _stable_id("failure", payload)
