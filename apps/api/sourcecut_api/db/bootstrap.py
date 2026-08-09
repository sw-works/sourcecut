from __future__ import annotations

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.telemetry import configure_telemetry, force_flush_telemetry, telemetry_span


def main() -> None:
    configure_telemetry()
    client = get_clickhouse_client()
    try:
        with telemetry_span(
            "sourcecut.admin.migrations",
            {"sourcecut.access.path": "direct_admin"},
        ):
            applied = bootstrap_database(client)
    finally:
        force_flush_telemetry()
        client.close()

    if applied:
        versions = ", ".join(migration.version for migration in applied)
        print(f"Applied {len(applied)} migration(s): {versions}")
    else:
        print("Database schema is already up to date")


if __name__ == "__main__":
    main()
