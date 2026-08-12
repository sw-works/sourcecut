from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, Literal


class FakeClickHouseClient:
    def __init__(
        self,
        mode: Literal["corpus", "migrations", "media"],
    ) -> None:
        self.mode = mode
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.views: set[str] = set()
        self.migrations: list[tuple[str, str]] = []
        self.insert_settings: list[dict[str, Any] | None] = []
        self.queries: list[str] = []
        self.query_count = 0

    @property
    def rows(self) -> list[dict[str, Any]]:
        return self.tables.setdefault("media_assets", [])

    @property
    def settings(self) -> dict[str, Any] | None:
        return self.insert_settings[-1] if self.insert_settings else None

    def command(self, sql: str) -> None:
        if self.mode != "migrations":
            raise AssertionError("command is available only in migrations mode")
        match = re.search(r"CREATE TABLE IF NOT EXISTS\s+([a-z_]+)", sql)
        replacement = re.search(r"CREATE OR REPLACE TABLE\s+([a-z_]+)", sql)
        view = re.search(r"CREATE VIEW IF NOT EXISTS\s+([a-z_]+)", sql)
        replacement_view = re.search(r"CREATE OR REPLACE VIEW\s+([a-z_]+)", sql)
        materialized_view = re.search(
            r"CREATE MATERIALIZED VIEW IF NOT EXISTS\s+([a-z_]+)", sql
        )
        dictionary = re.search(r"CREATE DICTIONARY IF NOT EXISTS\s+([a-z_]+)", sql)
        alteration = re.search(r"ALTER TABLE\s+([a-z_]+)", sql)
        commands = (
            match,
            replacement,
            view,
            replacement_view,
            materialized_view,
            dictionary,
            alteration,
        )
        if all(item is None for item in commands):
            raise AssertionError(f"Unexpected command: {sql}")
        if match is not None:
            self.tables.setdefault(match.group(1), [])
        elif replacement is not None and replacement.group(1) not in self.tables:
            raise AssertionError(f"Cannot replace missing table: {replacement.group(1)}")
        elif view is not None:
            self.views.add(view.group(1))
        elif replacement_view is not None:
            self.views.add(replacement_view.group(1))
        elif materialized_view is not None:
            self.views.add(materialized_view.group(1))
        elif dictionary is not None:
            self.views.add(dictionary.group(1))
        elif alteration is not None and alteration.group(1) not in self.tables:
            raise AssertionError(f"Cannot alter missing table: {alteration.group(1)}")

    def query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> SimpleNamespace:
        self.queries.append(query)
        if self.mode == "migrations":
            expected = "SELECT version, checksum FROM sourcecut_schema_migrations ORDER BY version"
            assert query == expected
            rows = [(version, checksum.encode("ascii")) for version, checksum in self.migrations]
            return SimpleNamespace(result_rows=rows)
        resolved = parameters or {}
        if self.mode == "media":
            self.query_count += 1
            assert "FROM media_assets" in query
            return SimpleNamespace(
                result_rows=[
                    (row["asset_id"], row["metadata_sha256"])
                    for row in self.rows
                    if row["asset_id"] in resolved["ids"]
                ]
            )
        table = next(
            table
            for table in (
                "sources",
                "journal_entries",
                "passages",
                "observations",
                "extraction_runs",
                "extraction_failures",
                "raw_source_documents",
                "text_units",
                "classical_passages",
                "linguistic_annotation_releases",
                "text_tokens",
                "formula_occurrences",
            )
            if f"FROM {table}" in query
        )
        records = self.tables.get(table, [])
        if table == "extraction_runs":
            matching = [
                record
                for record in records
                if record["idempotency_key"] == resolved["idempotency_key"]
            ]
            matching.sort(key=lambda record: record["started_at"], reverse=True)
            rows = [(record["run_id"], record["status"]) for record in matching[:1]]
        elif table in {"observations", "extraction_failures"}:
            id_field = "observation_id" if table == "observations" else "failure_id"
            rows = [
                (record[id_field],)
                for record in records
                if record["passage_id"] == resolved["passage_id"]
                and record[id_field] in resolved["ids"]
            ]
        else:
            fields = {
                "sources": ("source_id", "content_sha256"),
                "journal_entries": ("entry_id", "raw_text_sha256"),
                "passages": ("passage_id", "passage_sha256"),
                "raw_source_documents": ("document_id", "raw_sha256"),
                "text_units": ("text_unit_id", "text_sha256"),
                "classical_passages": ("passage_id", "passage_sha256"),
                "linguistic_annotation_releases": (
                    "annotation_release_id",
                    "source_sha256",
                ),
                "text_tokens": ("token_id", "token_sha256"),
                "formula_occurrences": ("occurrence_id", "occurrence_sha256"),
            }[table]
            rows = [
                (record[fields[0]], record[fields[1]])
                for record in records
                if record[fields[0]] in resolved["ids"]
            ]
        return SimpleNamespace(result_rows=rows)

    def insert(
        self,
        table: str,
        data: list[list[object]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
    ) -> None:
        if self.mode == "migrations":
            assert table == "sourcecut_schema_migrations"
            assert column_names == ["version", "name", "checksum", "applied_at"]
            self.migrations.append((str(data[0][0]), str(data[0][2])))
            return
        if self.mode == "media":
            assert table == "media_assets"
        self.insert_settings.append(settings)
        self.tables.setdefault(table, []).extend(
            dict(zip(column_names, row, strict=True)) for row in data
        )
