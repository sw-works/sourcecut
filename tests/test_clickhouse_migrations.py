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
        self.views: set[str] = set()
        self.migrations: list[tuple[str, str]] = []

    def command(self, sql: str) -> None:
        match = re.search(r"CREATE TABLE IF NOT EXISTS\s+([a-z_]+)", sql)
        replacement = re.search(r"CREATE OR REPLACE TABLE\s+([a-z_]+)", sql)
        view = re.search(r"CREATE VIEW IF NOT EXISTS\s+([a-z_]+)", sql)
        replacement_view = re.search(r"CREATE OR REPLACE VIEW\s+([a-z_]+)", sql)
        materialized_view = re.search(
            r"CREATE MATERIALIZED VIEW IF NOT EXISTS\s+([a-z_]+)", sql
        )
        alteration = re.search(r"ALTER TABLE\s+([a-z_]+)", sql)
        if all(
            item is None
            for item in (
                match,
                replacement,
                view,
                replacement_view,
                materialized_view,
                alteration,
            )
        ):
            raise AssertionError(f"Unexpected command: {sql}")
        if match is not None:
            self.tables.add(match.group(1))
        elif replacement is not None and replacement.group(1) not in self.tables:
            raise AssertionError(f"Cannot replace missing table: {replacement.group(1)}")
        elif view is not None:
            self.views.add(view.group(1))
        elif replacement_view is not None:
            self.views.add(replacement_view.group(1))
        elif materialized_view is not None:
            self.views.add(materialized_view.group(1))
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

    assert len(applied) == 51
    assert EXPECTED_TABLES <= client.tables
    assert "sourcecut_schema_migrations" in client.tables
    assert [migration.version for migration in applied] == [
        f"{number:03}" for number in range(1, 52)
    ]
    assert client.views == {
        "author_term_presence",
        "evidence_window",
        "passage_lookup",
        "research_stage_stats_mv",
    }


def test_bootstrap_is_idempotent() -> None:
    client = FakeClickHouseClient()

    first = bootstrap_database(client)  # type: ignore[arg-type]
    second = bootstrap_database(client)  # type: ignore[arg-type]

    assert len(first) == 51
    assert second == ()
    assert len(client.migrations) == 51


def test_bootstrap_rejects_changed_applied_migration() -> None:
    client = FakeClickHouseClient()
    bootstrap_database(client)  # type: ignore[arg-type]
    client.migrations[0] = ("001", "0" * 64)

    with pytest.raises(MigrationDriftError, match="001"):
        bootstrap_database(client)  # type: ignore[arg-type]


def test_migration_files_are_single_statements() -> None:
    migrations = load_migrations()

    assert len(migrations) == 51
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
    assert "tokenbf_v1(8192, 3, 0)" in migrations[11].sql
    assert "MATERIALIZE INDEX idx_passage_text_tokens" in migrations[12].sql
    assert "ADD PROJECTION by_passage_id" in migrations[17].sql
    assert "MATERIALIZE PROJECTION by_passage_id" in migrations[18].sql
    assert "INTERVAL 90 DAY DELETE" in migrations[19].sql
    assert "CODEC(ZSTD(3))" in migrations[20].sql
    assert "CODEC(Delta, ZSTD)" in migrations[22].sql
    assert "lower(passage_text)" in migrations[28].sql
    assert "MATERIALIZE INDEX idx_passage_text_lower_tokens" in migrations[29].sql
    assert "DROP INDEX idx_passage_text_tokens" in migrations[34].sql
    assert "CREATE VIEW IF NOT EXISTS evidence_window" in migrations[37].sql
    assert "CREATE VIEW IF NOT EXISTS author_term_presence" in migrations[38].sql
    assert "CREATE VIEW IF NOT EXISTS passage_lookup" in migrations[39].sql
    assert "ReplacingMergeTree(ingested_at)" in migrations[40].sql
    assert "PARTITION BY intDiv(entry_date, 10000)" in migrations[40].sql
    assert "PROJECTION by_passage_id" in migrations[41].sql
    assert "ReplacingMergeTree(created_at)" in migrations[42].sql
    assert "raw_metadata JSON" in migrations[43].sql
    assert all(" FINAL" in migration.sql for migration in migrations[44:47])
    assert "ReplacingMergeTree(updated_at)" in migrations[47].sql
    assert "ADD COLUMN IF NOT EXISTS duration_ms" in migrations[48].sql
    assert "AggregatingMergeTree" in migrations[49].sql
    assert "countState()" in migrations[50].sql


def test_invalid_migration_filename_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.sql").write_text("SELECT 1", encoding="utf-8")

    with pytest.raises(MigrationError, match="Invalid migration filename"):
        load_migrations(tmp_path)
