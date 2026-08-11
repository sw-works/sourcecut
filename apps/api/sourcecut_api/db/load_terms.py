from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database

DEFAULT_PATH = Path("data/reference/term_expansions.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load curated term expansions")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    records = json.loads(args.path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    rows = [
        [item["category"], item["term"], item["expansions"], item.get("notes", ""), now]
        for item in records
    ]
    client = get_clickhouse_client()
    try:
        bootstrap_database(client)
        client.insert(
            "term_expansions",
            rows,
            column_names=["category", "term", "expansions", "notes", "updated_at"],
            settings={"async_insert": 1, "wait_for_async_insert": 1},
        )
        client.command("SYSTEM RELOAD DICTIONARY sourcecut.term_expansion_dict")
    finally:
        client.close()
    print(f"Loaded {len(rows)} term expansion row(s).")
