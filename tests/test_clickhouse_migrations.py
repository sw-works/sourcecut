from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeClickHouseClient

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
    "route_waypoints",
    "media_assets",
    "entities",
    "entity_mentions",
    "corpora",
    "licenses",
    "works",
    "source_versions",
    "raw_source_documents",
    "text_units",
    "classical_passages",
}


def test_empty_database_bootstraps_all_task_tables() -> None:
    client = FakeClickHouseClient("migrations")

    applied = bootstrap_database(client)  # type: ignore[arg-type]

    assert len(applied) == 76
    assert EXPECTED_TABLES <= client.tables.keys()
    assert "sourcecut_schema_migrations" in client.tables
    assert [migration.version for migration in applied] == [
        f"{number:03}" for number in range(1, 77)
    ]
    assert client.views == {
        "author_term_presence",
        "author_date_matrix",
        "evidence_window",
        "entity_mentions_window",
        "passage_lookup",
        "research_stage_stats_mv",
        "term_expansion_dict",
        "odyssey_text_lookup_v",
        "odyssey_passage_context_v",
    }


def test_bootstrap_is_idempotent() -> None:
    client = FakeClickHouseClient("migrations")

    first = bootstrap_database(client)  # type: ignore[arg-type]
    second = bootstrap_database(client)  # type: ignore[arg-type]

    assert len(first) == 76
    assert second == ()
    assert len(client.migrations) == 76


def test_bootstrap_rejects_changed_applied_migration() -> None:
    client = FakeClickHouseClient("migrations")
    bootstrap_database(client)  # type: ignore[arg-type]
    client.migrations[0] = ("001", "0" * 64)

    with pytest.raises(MigrationDriftError, match="001"):
        bootstrap_database(client)  # type: ignore[arg-type]


def test_migration_files_are_single_statements() -> None:
    migrations = load_migrations()

    assert len(migrations) == 76
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
    assert "embedding Array(Float32)" in migrations[51].sql
    assert "embedding_model LowCardinality(String)" in migrations[52].sql
    assert "embedding Array(Float32)" in migrations[53].sql
    assert "embedding_model LowCardinality(String)" in migrations[54].sql
    assert "ReplacingMergeTree(updated_at)" in migrations[55].sql
    assert "COMPLEX_KEY_HASHED" in migrations[56].sql
    assert "CREATE TABLE IF NOT EXISTS entities" in migrations[57].sql
    assert "ReplacingMergeTree(created_at)" in migrations[58].sql
    assert "CREATE VIEW IF NOT EXISTS entity_mentions_window" in migrations[59].sql
    assert "CREATE VIEW IF NOT EXISTS author_date_matrix" in migrations[60].sql
    assert "e.author_id AS author_id" in migrations[61].sql
    assert "CREATE TABLE IF NOT EXISTS route_waypoints" in migrations[62].sql
    assert "hasAnyTokens" in migrations[66].sql
    assert "ReplacingMergeTree(updated_at)" in migrations[67].sql
    assert "ORDER BY (status, corpus_id)" in migrations[67].sql
    assert "commercial_use_allowed Int8 DEFAULT -1" in migrations[68].sql
    assert "book_count UInt16" in migrations[69].sql
    assert "metadata JSON" in migrations[69].sql
    assert "version_type Enum8" in migrations[70].sql
    assert "source_sha256 Nullable(FixedString(64))" in migrations[70].sql
    assert "ORDER BY (work_id, version_type, language, version_id)" in migrations[70].sql
    assert "raw_content String CODEC(ZSTD(3))" in migrations[71].sql
    assert all("PARTITION BY" not in migration.sql for migration in migrations[67:72])
    assert "ORDER BY (version_id, book, line_start, text_unit_id)" in migrations[72].sql
    assert "original_text String CODEC(ZSTD(3))" in migrations[72].sql
    assert "ORDER BY (version_id, book, line_start, passage_id)" in migrations[73].sql
    assert "CREATE VIEW IF NOT EXISTS odyssey_text_lookup_v" in migrations[74].sql
    assert "FROM text_units FINAL" in migrations[74].sql
    assert "CREATE VIEW IF NOT EXISTS odyssey_passage_context_v" in migrations[75].sql
    assert all("PARTITION BY" not in migration.sql for migration in migrations[72:76])


def test_invalid_migration_filename_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "bad.sql").write_text("SELECT 1", encoding="utf-8")

    with pytest.raises(MigrationError, match="Invalid migration filename"):
        load_migrations(tmp_path)
