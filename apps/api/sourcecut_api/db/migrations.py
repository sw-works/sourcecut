from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MIGRATIONS_DIR = PROJECT_ROOT / "sql" / "clickhouse"
MIGRATION_FILENAME = re.compile(r"^(?P<version>\d{3})_(?P<name>[a-z0-9_]+)\.sql$")

CREATE_MIGRATION_LEDGER = """
CREATE TABLE IF NOT EXISTS sourcecut_schema_migrations
(
    version String,
    name String,
    checksum FixedString(64),
    applied_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY version
""".strip()


class MigrationError(RuntimeError):
    pass


class MigrationDriftError(MigrationError):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    name: str
    sql: str
    checksum: str


def load_migrations(directory: Path = DEFAULT_MIGRATIONS_DIR) -> tuple[Migration, ...]:
    migrations: list[Migration] = []
    seen_versions: set[str] = set()

    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_FILENAME.fullmatch(path.name)
        if match is None:
            raise MigrationError(f"Invalid migration filename: {path.name}")
        version = match.group("version")
        if version in seen_versions:
            raise MigrationError(f"Duplicate migration version: {version}")
        sql = path.read_text(encoding="utf-8").strip()
        if not sql:
            raise MigrationError(f"Migration is empty: {path.name}")
        seen_versions.add(version)
        migrations.append(
            Migration(
                version=version,
                name=match.group("name"),
                sql=sql,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            )
        )

    if not migrations:
        raise MigrationError(f"No migrations found in {directory}")
    return tuple(migrations)


def _checksum_text(value: str | bytes) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii")
    return value


def bootstrap_database(
    client: Client,
    migrations: tuple[Migration, ...] | None = None,
) -> tuple[Migration, ...]:
    resolved_migrations = migrations or load_migrations()
    client.command(CREATE_MIGRATION_LEDGER)
    rows = client.query(
        "SELECT version, checksum FROM sourcecut_schema_migrations ORDER BY version"
    ).result_rows
    applied = {str(version): _checksum_text(checksum) for version, checksum in rows}
    newly_applied: list[Migration] = []

    for migration in resolved_migrations:
        existing_checksum = applied.get(migration.version)
        if existing_checksum is not None:
            if existing_checksum != migration.checksum:
                raise MigrationDriftError(
                    f"Migration {migration.version} was changed after it was applied"
                )
            continue

        client.command(migration.sql)
        client.insert(
            "sourcecut_schema_migrations",
            [[migration.version, migration.name, migration.checksum, datetime.now(UTC)]],
            column_names=["version", "name", "checksum", "applied_at"],
        )
        newly_applied.append(migration)

    return tuple(newly_applied)
