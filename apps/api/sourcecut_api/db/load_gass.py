from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pipelines.journals.gass import SOURCE_ID, SOURCE_URL, parse_gass_entries
from pipelines.journals.gutenberg import read_gutenberg_text, serialize_entries
from pipelines.journals.passages import segment_entries
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.models import SourceRecord
from sourcecut_api.repositories import ClickHouseCorpusRepository


def build_source_record(entries_bytes: bytes) -> SourceRecord:
    return SourceRecord(
        source_id=SOURCE_ID,
        provider="Internet Archive / New York Public Library",
        title="Gass's Journal of the Lewis and Clark Expedition",
        source_url=SOURCE_URL,
        edition_notes="1904 James Kendall Hosmer edition, reprinted from the 1811 edition",
        rights_status="Public domain in the USA",
        raw_metadata=json.dumps(
            {"archive_identifier": "gasssjournalofle00gass", "source_url": SOURCE_URL},
            separators=(",", ":"),
            sort_keys=True,
        ),
        content_sha256=hashlib.sha256(entries_bytes).hexdigest(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the public-domain Patrick Gass journal")
    parser.add_argument("path", type=Path, help="Cached Internet Archive OCR text")
    args = parser.parse_args()

    entries = parse_gass_entries(read_gutenberg_text(args.path))
    entries_bytes = serialize_entries(entries)
    passages = segment_entries(entries)
    client = get_clickhouse_client()
    try:
        result = ClickHouseCorpusRepository(client).load_corpus(
            [build_source_record(entries_bytes)],
            entries,
            passages,
        )
    finally:
        client.close()
    print(
        f"Inserted {result.sources_inserted} source(s), "
        f"{result.entries_inserted} Gass entry/entries, and "
        f"{result.passages_inserted} passage(s)."
    )
