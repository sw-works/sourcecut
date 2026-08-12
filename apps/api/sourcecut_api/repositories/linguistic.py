from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

    from pipelines.classics.treebank import ParsedLinguistics


class LinguisticDriftError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LinguisticLoadResult:
    releases_inserted: int
    tokens_inserted: int
    formulae_inserted: int


class ClickHouseLinguisticRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load(self, parsed: ParsedLinguistics) -> LinguisticLoadResult:
        releases = self._missing(
            "linguistic_annotation_releases",
            "annotation_release_id",
            "source_sha256",
            [parsed.release],
        )
        tokens = self._missing("text_tokens", "token_id", "token_sha256", list(parsed.tokens))
        formulae = self._missing(
            "formula_occurrences",
            "occurrence_id",
            "occurrence_sha256",
            list(parsed.formulae),
        )
        now = datetime.now(UTC)
        self._insert(
            "linguistic_annotation_releases",
            [
                "annotation_release_id", "work_id", "source_version_id", "annotation_source",
                "annotation_version", "source_document_urn", "repository_url", "upstream_path",
                "upstream_revision", "source_sha256", "license_id", "raw_content",
                "review_status", "ingested_at",
            ],
            [[
                item.annotation_release_id, item.work_id, item.source_version_id,
                item.annotation_source, item.annotation_version, item.source_document_urn,
                item.repository_url, item.upstream_path, item.upstream_revision,
                item.source_sha256, item.license_id, item.raw_content, item.review_status, now,
            ] for item in releases],
        )
        self._insert(
            "text_tokens",
            [
                "token_id", "text_unit_id", "version_id", "book", "line", "token_index",
                "surface", "normalized_surface", "accentless_surface", "lemma", "lemma_search",
                "part_of_speech", "morphology", "char_start", "char_end", "annotation_source",
                "annotation_confidence", "review_status", "annotation_version",
                "annotation_release_id", "source_token_ref", "token_sha256", "updated_at",
            ],
            [[
                item.token_id, item.text_unit_id, item.version_id, item.book, item.line,
                item.token_index, item.surface, item.normalized_surface, item.accentless_surface,
                item.lemma, item.lemma_search, item.part_of_speech,
                json.dumps(item.morphology, ensure_ascii=False, sort_keys=True), item.char_start,
                item.char_end, item.annotation_source, item.annotation_confidence,
                item.review_status, item.annotation_version, item.annotation_release_id,
                item.source_token_ref, item.token_sha256, now,
            ] for item in tokens],
        )
        self._insert(
            "formula_occurrences",
            [
                "occurrence_id", "formula_id", "version_id", "book", "line_start", "line_end",
                "ngram_size", "normalized_formula", "display_formula", "token_ids",
                "occurrence_sha256", "derived_method", "review_status", "created_at",
            ],
            [[
                item.occurrence_id, item.formula_id, item.version_id, item.book,
                item.line_start, item.line_end, item.ngram_size, item.normalized_formula,
                item.display_formula, list(item.token_ids), item.occurrence_sha256,
                item.derived_method, item.review_status, now,
            ] for item in formulae],
        )
        return LinguisticLoadResult(len(releases), len(tokens), len(formulae))

    def _missing(
        self,
        table: str,
        id_field: str,
        hash_field: str,
        records: list[object],
    ) -> list[object]:
        if not records:
            return []
        rows = []
        ids = [getattr(item, id_field) for item in records]
        for start in range(0, len(ids), 10_000):
            rows.extend(
                self._client.query(
                    f"SELECT {id_field}, {hash_field} FROM {table} "
                    f"WHERE {id_field} IN {{ids:Array(String)}}",
                    parameters={"ids": ids[start : start + 10_000]},
                ).result_rows
            )
        existing = {str(row[0]): _hash_text(row[1]) for row in rows}
        missing = []
        for record in records:
            record_id = str(getattr(record, id_field))
            expected = str(getattr(record, hash_field))
            if record_id not in existing:
                missing.append(record)
            elif existing[record_id] != expected:
                raise LinguisticDriftError(f"{table}.{record_id} has a different hash")
        return missing

    def _insert(self, table: str, columns: Sequence[str], rows: list[list[object]]) -> None:
        for start in range(0, len(rows), 10_000):
            batch = rows[start : start + 10_000]
            if batch:
                self._client.insert(table, batch, column_names=list(columns))


def _hash_text(value: str | bytes) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else value
