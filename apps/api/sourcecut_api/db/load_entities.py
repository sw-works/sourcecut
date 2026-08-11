from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database

DEFAULT_PATH = Path("data/reference/entities.json")


def validate_mention(text: str, quote: str, start: int, end: int) -> bool:
    return 0 <= start < end <= len(text) and text[start:end] == quote


def extract_exact_mentions(
    passage: dict[str, Any], entities: list[dict[str, Any]]
) -> list[list[object]]:
    text = str(passage["passage_text"])
    created_at = datetime.now(UTC)
    rows: list[list[object]] = []
    seen: set[tuple[str, int, int]] = set()
    for entity in entities:
        for name in entity["alt_names"]:
            for match in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.IGNORECASE):
                key = (entity["entity_id"], match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                payload = f"{passage['passage_id']}\0{key[0]}\0{key[1]}\0{key[2]}"
                mention_id = f"mention:{hashlib.sha256(payload.encode()).hexdigest()}"
                quote = text[match.start() : match.end()]
                valid = validate_mention(text, quote, match.start(), match.end())
                rows.append([
                    mention_id,
                    entity["entity_id"],
                    passage["passage_id"],
                    passage["entry_date"],
                    passage["author_id"],
                    quote,
                    match.start(),
                    match.end(),
                    valid,
                    "valid" if valid else "invalid",
                    "code",
                    "deterministic",
                    "entity-mention-v1",
                    "entity-exact-v1",
                    created_at,
                ])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Load entity registry and exact mentions")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    entities = json.loads(args.path.read_text(encoding="utf-8"))
    client = get_clickhouse_client()
    try:
        bootstrap_database(client)
        now = datetime.now(UTC)
        client.insert(
            "entities",
            [
                [
                    e["entity_id"],
                    e["entity_type"],
                    e["canonical_name"],
                    e["alt_names"],
                    e["notes"],
                    now,
                ]
                for e in entities
            ],
            column_names=[
                "entity_id",
                "entity_type",
                "canonical_name",
                "alt_names",
                "notes",
                "updated_at",
            ],
            settings={"async_insert": 1, "wait_for_async_insert": 1},
        )
        result = client.query(
            "SELECT passage_id, entry_date, author_id, passage_text FROM passages FINAL"
        )
        passages = [
            dict(zip(result.column_names, row, strict=True)) for row in result.result_rows
        ]
        mentions = [
            row
            for passage in passages
            for row in extract_exact_mentions(passage, entities)
        ]
        if mentions:
            client.insert(
                "entity_mentions",
                mentions,
                column_names=["mention_id","entity_id","passage_id","entry_date","author_id","source_quote","source_start","source_end","trusted","validation_status","extractor","model","schema_version","prompt_version","created_at"],
                settings={"async_insert": 1, "wait_for_async_insert": 1},
            )
    finally:
        client.close()
    print(f"Loaded {len(entities)} entities and {len(mentions)} exact mention(s).")
