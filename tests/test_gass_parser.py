from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from pipelines.journals.gass import PARSER_VERSION, SOURCE_ID, parse_gass_entries
from pipelines.journals.gutenberg import (
    parse_journal_entries,
    read_gutenberg_text,
    serialize_entries,
)
from pipelines.journals.passages import segment_entry

FIXTURE = Path("fixtures/journals/gass_1904_september_1805_excerpt.txt")
GUTENBERG_FIXTURE = Path("fixtures/journals/gutenberg_8419_september_21_1805.txt")
GUTENBERG_SERIALIZED_SHA256 = "8f0e07c93fe545e31ae15898b584b8b9188d850bb806fed25b919a2d5912c0fa"


def test_gass_ocr_headings_resolve_to_monotonic_dates() -> None:
    entries = parse_gass_entries(read_gutenberg_text(FIXTURE))

    assert len(entries) == 17
    assert entries[0].entry_date == date(1805, 9, 1)
    assert entries[14].entry_date == date(1805, 9, 15)
    assert entries[15].entry_date == date(1805, 9, 16)
    assert entries[16].entry_date == date(1805, 9, 17)
    assert entries[14].heading == "SUNDAY i$tb."
    assert all(entry.ordinal_for_day == 1 for entry in entries)


def test_gass_ids_hashes_and_parser_provenance_are_deterministic() -> None:
    first = parse_gass_entries(read_gutenberg_text(FIXTURE))
    second = parse_gass_entries(read_gutenberg_text(FIXTURE))

    assert first == second
    assert first[-1].entry_id == f"{SOURCE_ID}:gass:1805-09-17:1"
    assert first[-1].parser_version == PARSER_VERSION
    assert first[-1].raw_text_sha256 == hashlib.sha256(first[-1].raw_text.encode()).hexdigest()


def test_gass_passages_reconstruct_each_selected_entry_exactly() -> None:
    entries = parse_gass_entries(read_gutenberg_text(FIXTURE))

    for entry in entries[14:]:
        passages = segment_entry(entry)
        assert "".join(passage.passage_text for passage in passages) == entry.raw_text
        assert passages[0].char_start == 0
        assert passages[-1].char_end == len(entry.raw_text)


def test_8419_serialization_regression_is_byte_identical() -> None:
    text = read_gutenberg_text(GUTENBERG_FIXTURE)
    serialized = serialize_entries(parse_journal_entries(text))

    assert hashlib.sha256(serialized).hexdigest() == GUTENBERG_SERIALIZED_SHA256
