from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sourcecut_api.models.classical_text import ClassicalPassage

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

    from pipelines.classics.tei import ParsedOdysseyVersion


class ClassicalTextDriftError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ClassicalTextLoadResult:
    documents_inserted: int
    units_inserted: int
    passages_inserted: int


class ClickHouseClassicalTextRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load_version(
        self,
        parsed: ParsedOdysseyVersion,
        passages: Sequence[ClassicalPassage],
    ) -> ClassicalTextLoadResult:
        document = parsed.document
        documents = self._missing_by_hash(
            "raw_source_documents",
            "document_id",
            "raw_sha256",
            [document],
        )
        units = self._missing_by_hash(
            "text_units", "text_unit_id", "text_sha256", list(parsed.units)
        )
        passage_rows = self._missing_by_hash(
            "classical_passages", "passage_id", "passage_sha256", list(passages)
        )
        now = datetime.now(UTC)
        self._insert(
            "raw_source_documents",
            (
                "document_id",
                "version_id",
                "media_type",
                "raw_content",
                "raw_sha256",
                "upstream_path",
                "upstream_revision",
                "ingested_at",
            ),
            [
                [
                    item.document_id,
                    item.version_id,
                    item.media_type,
                    item.raw_content,
                    item.raw_sha256,
                    item.upstream_path,
                    item.upstream_revision,
                    now,
                ]
                for item in documents
            ],
        )
        self._insert(
            "text_units",
            (
                "text_unit_id",
                "work_id",
                "version_id",
                "book",
                "line_start",
                "line_end",
                "source_line_start",
                "source_line_end",
                "citation_correction",
                "citation",
                "cts_urn",
                "unit_index",
                "original_text",
                "normalized_text",
                "source_document_id",
                "source_char_start",
                "source_char_end",
                "text_sha256",
                "parser_version",
                "ingested_at",
            ),
            [
                [
                    item.text_unit_id,
                    item.work_id,
                    item.version_id,
                    item.book,
                    item.line_start,
                    item.line_end,
                    item.source_line_start,
                    item.source_line_end,
                    item.citation_correction,
                    item.citation,
                    item.cts_urn,
                    item.unit_index,
                    item.original_text,
                    item.normalized_text,
                    item.source_document_id,
                    item.source_char_start,
                    item.source_char_end,
                    item.text_sha256,
                    item.parser_version,
                    now,
                ]
                for item in units
            ],
        )
        self._insert(
            "classical_passages",
            (
                "passage_id",
                "version_id",
                "book",
                "line_start",
                "line_end",
                "unit_ids",
                "passage_text",
                "passage_sha256",
                "segmentation_version",
                "created_at",
            ),
            [
                [
                    item.passage_id,
                    item.version_id,
                    item.book,
                    item.line_start,
                    item.line_end,
                    list(item.unit_ids),
                    item.passage_text,
                    item.passage_sha256,
                    item.segmentation_version,
                    now,
                ]
                for item in passage_rows
            ],
        )
        return ClassicalTextLoadResult(
            documents_inserted=len(documents),
            units_inserted=len(units),
            passages_inserted=len(passage_rows),
        )

    def _missing_by_hash(
        self,
        table: str,
        id_field: str,
        hash_field: str,
        records: list[object],
    ) -> list[object]:
        if not records:
            return []
        ids = [getattr(record, id_field) for record in records]
        rows = self._client.query(
            f"SELECT {id_field}, {hash_field} FROM {table} "
            f"WHERE {id_field} IN {{ids:Array(String)}}",
            parameters={"ids": ids},
        ).result_rows
        existing = {str(row[0]): _hash_text(row[1]) for row in rows}
        missing: list[object] = []
        for record in records:
            record_id = str(getattr(record, id_field))
            expected_hash = str(getattr(record, hash_field))
            actual_hash = existing.get(record_id)
            if actual_hash is None:
                missing.append(record)
            elif actual_hash != expected_hash:
                raise ClassicalTextDriftError(f"{table}.{record_id} has a different hash")
        return missing

    def _insert(
        self, table: str, columns: Sequence[str], rows: list[list[object]]
    ) -> None:
        for start in range(0, len(rows), 10_000):
            batch = rows[start : start + 10_000]
            if not batch:
                continue
            settings = (
                {"async_insert": 1, "wait_for_async_insert": 1}
                if len(batch) < 1_000
                else None
            )
            self._client.insert(
                table,
                batch,
                column_names=list(columns),
                settings=settings,
            )


def _hash_text(value: str | bytes) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else value
