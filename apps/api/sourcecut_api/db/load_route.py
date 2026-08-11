from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database

DEFAULT_PATH = Path("data/reference/route_sept_1805.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load curated September route waypoints")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    records = json.loads(args.path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    client = get_clickhouse_client()
    try:
        bootstrap_database(client)
        client.insert(
            "route_waypoints",
            [
                [
                    record["waypoint_id"],
                    record["entry_date"],
                    record["name"],
                    record["lat"],
                    record["lon"],
                    record["citation_passage_ids"],
                    record["source_note"],
                    now,
                ]
                for record in records
            ],
            column_names=[
                "waypoint_id",
                "entry_date",
                "name",
                "lat",
                "lon",
                "citation_passage_ids",
                "source_note",
                "updated_at",
            ],
            settings={"async_insert": 1, "wait_for_async_insert": 1},
        )
    finally:
        client.close()
    print(f"Loaded {len(records)} route waypoint(s).")
