from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pipelines.journals import (
    parse_journal_entries,
    read_gutenberg_text,
    segment_entries,
    serialize_entries,
)
from pipelines.journals.gutenberg import GUTENBERG_EBOOK_ID, SOURCE_ID, SOURCE_URL
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.models import SourceRecord
from sourcecut_api.repositories import ClickHouseCorpusRepository


def build_source_record(entries_bytes: bytes) -> SourceRecord:
    return SourceRecord(
        source_id=SOURCE_ID,
        provider="Project Gutenberg",
        title="The Journals of Lewis and Clark, 1804-1806",
        source_url=SOURCE_URL,
        edition_notes="Project Gutenberg eBook #8419",
        rights_status="Public domain in the USA",
        raw_metadata=json.dumps(
            {"ebook_id": GUTENBERG_EBOOK_ID, "source_url": SOURCE_URL},
            separators=(",", ":"),
            sort_keys=True,
        ),
        content_sha256=hashlib.sha256(entries_bytes).hexdigest(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load an authentic Gutenberg journal corpus")
    parser.add_argument("path", type=Path, help="Cached Project Gutenberg UTF-8 text file")
    args = parser.parse_args()

    entries = parse_journal_entries(read_gutenberg_text(args.path))
    entries_bytes = serialize_entries(entries)
    passages = segment_entries(entries)
    repository = ClickHouseCorpusRepository(get_clickhouse_client())
    result = repository.load_corpus(
        [build_source_record(entries_bytes)],
        entries,
        passages,
    )
    print(
        f"Inserted {result.sources_inserted} source(s), "
        f"{result.entries_inserted} journal entry/entries, and "
        f"{result.passages_inserted} passage(s)."
    )
