from __future__ import annotations

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database


def main() -> None:
    client = get_clickhouse_client()
    try:
        applied = bootstrap_database(client)
    finally:
        client.close()

    if applied:
        versions = ", ".join(migration.version for migration in applied)
        print(f"Applied {len(applied)} migration(s): {versions}")
    else:
        print("Database schema is already up to date")


if __name__ == "__main__":
    main()
