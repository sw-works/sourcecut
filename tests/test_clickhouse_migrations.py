from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from sourcecut_api.db.migrations import (
    MigrationDriftError,
    MigrationError,
    bootstrap_database,
    load_migrations,
)

EXPECTED_TABLES = {
    "sources",
    "journal_entries",
    "passages",
    "observations",
    "extraction_runs",
    "extraction_failures",
    "research_events",
    "media_assets",
}


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.tables: set[str] = set()
        self.migrations: list[tuple[str, str]] = []

    def command(self, sql: str) -> None:
        match = re.search(r"CREATE TABLE IF NOT EXISTS\s+([a-z_]+)", sql)
        replacement = re.search(r"CREATE OR REPLACE TABLE\s+([a-z_]+)", sql)
        alteration = re.search(r"ALTER TABLE\s+([a-z_]+)\s+ADD COLUMN", sql)
        if match is None and replacement is None and alteration is None:
            raise AssertionError(f"Unexpected command: {sql}")
        if match is not None:
            self.tables.add(match.group(1))
        elif replacement is not None and replacement.group(1) not in self.tables:
            raise AssertionError(f"Cannot replace missing table: {replacement.group(1)}")
        elif alteration is not None and alteration.group(1) not in self.tables:
            raise AssertionError(f"Cannot alter missing table: {alteration.group(1)}")

    def query(self, sql: str) -> SimpleNamespace:
        assert sql == "SELECT version, checksum FROM sourcecut_schema_migrations ORDER BY version"
        rows = [(version, checksum.encode("ascii")) for version, checksum in self.migrations]
        return SimpleNamespace(result_rows=rows)

    def insert(
        self,
        table: str,
        rows: list[list[object]],
        column_names: list[str],
    ) -> None:
        assert table == "sourcecut_schema_migrations"
        assert column_names == ["version", "name", "checksum", "applied_at"]
        self.migrations.append((str(rows[0][0]), str(rows[0][2])))


def test_empty_database_bootstraps_all_task_tables() -> None:
    client = FakeClickHouseClient()

    applied = bootstrap_database(client)  # type: ignore[arg-type]

    assert len(applied) == 11
    assert EXPECTED_TABLES <= client.tables
    assert "sourcecut_schema_migrations" in client.tables
    assert [migration.version for migration in applied] == [
        f"{number:03}" for number in range(1, 12)
    ]


def test_bootstrap_is_idempotent() -> None:
    client = FakeClickHouseClient()

    first = bootstrap_database(client)  # type: ignore[arg-type]
    second = bootstrap_database(client)  # type: ignore[arg-type]

    assert len(first) == 11
    assert second == ()
    assert len(client.migrations) == 11


def test_bootstrap_rejects_changed_applied_migration() -> None:
    client = FakeClickHouseClient()
    bootstrap_database(client)  # type: ignore[arg-type]
    client.migrations[0] = ("001", "0" * 64)

    with pytest.raises(MigrationDriftError, match="001"):
        bootstrap_database(client)  # type: ignore[arg-type]


def test_migration_files_are_single_statements() -> None:
    migrations = load_migrations()

    assert len(migrations) == 11
    for migration in migrations:
        assert migration.sql.count(";") == 1

    assert all(
        "CREATE TABLE IF NOT EXISTS" in migration.sql for migration in migrations[:7]
    )
    assert "CREATE OR REPLACE TABLE journal_entries" in migrations[7].sql
    assert "entry_date Int32" in migrations[7].sql
    assert "CREATE OR REPLACE TABLE passages" in migrations[8].sql
    assert "entry_date Int32" in migrations[8].sql
    assert "ADD COLUMN IF NOT EXISTS validation_status" in migrations[9].sql
    assert "CREATE TABLE IF NOT EXISTS media_assets" in migrations[10].sql
    assert "PARTITION BY" not in migrations[10].sql


def test_invalid_migration_filename_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.sql").write_text("SELECT 1", encoding="utf-8")

    with pytest.raises(MigrationError, match="Invalid migration filename"):
        load_migrations(tmp_path)
