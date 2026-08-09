from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import pytest

from pipelines.journals.gutenberg import (
    GutenbergFormatError,
    parse_journal_entries,
    read_gutenberg_text,
    serialize_entries,
    strip_gutenberg_wrapper,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "journals"
    / "gutenberg_8419_september_21_1805.txt"
)


@pytest.fixture
def september_text() -> str:
    return read_gutenberg_text(FIXTURE)


def test_wrapper_is_removed(september_text: str) -> None:
    content = strip_gutenberg_wrapper(september_text)

    assert content.startswith("[Lewis, September 21, 1805]\n")
    assert content.endswith("Sick to day and puke which relive me.")
    assert "PROJECT GUTENBERG" not in content


def test_sampled_september_boundaries_are_exact(september_text: str) -> None:
    entries = parse_journal_entries(september_text)

    assert [
        (entry.author_id, entry.entry_date, entry.ordinal_for_day, entry.heading)
        for entry in entries
    ] == [
        ("lewis", date(1805, 9, 21), 1, "[Lewis, September 21, 1805]"),
        ("clark", date(1805, 9, 21), 1, "[Clark, September 21, 1805]"),
        ("clark", date(1805, 9, 21), 2, "[Clark, September 21, 1805]"),
    ]
    assert entries[0].raw_text.endswith("day S 30 W 15M.")
    assert entries[1].raw_text.endswith("gave him a Medal.")
    assert entries[2].raw_text.endswith("Sick to day and puke which relive me.")


def test_historical_text_is_not_modernized(september_text: str) -> None:
    entries = parse_journal_entries(september_text)

    assert "untill" in entries[0].raw_text
    assert "prarie woolf" in entries[0].raw_text
    assert "butifull Pine Countrey" in entries[2].raw_text
    assert re.search(r"\buntil\b", entries[0].raw_text) is None
    assert "beautiful Pine Country" not in entries[2].raw_text


def test_raw_text_hashes_are_exact(september_text: str) -> None:
    entries = parse_journal_entries(september_text)

    for entry in entries:
        assert entry.raw_text_sha256 == hashlib.sha256(entry.raw_text.encode("utf-8")).hexdigest()


def test_serialization_is_byte_deterministic_across_newline_styles(
    september_text: str,
) -> None:
    lf_bytes = serialize_entries(parse_journal_entries(september_text))
    crlf_bytes = serialize_entries(parse_journal_entries(september_text.replace("\n", "\r\n")))

    assert lf_bytes == crlf_bytes
    assert lf_bytes == serialize_entries(parse_journal_entries(september_text))


def test_other_diarist_heading_ends_supported_entry() -> None:
    text = """[Clark, May 17, 1804]
Clark text.
[Ordway, May 17, 1804]
Ordway text.
[Lewis, May 18, 1804]
Lewis text.
"""

    entries = parse_journal_entries(text)

    assert len(entries) == 2
    assert entries[0].raw_text == "Clark text."
    assert entries[1].raw_text == "Lewis text."


def test_one_sided_wrapper_is_rejected() -> None:
    text = """*** START OF THE PROJECT GUTENBERG EBOOK TEST ***
[Lewis, May 18, 1804]
Lewis text.
"""

    with pytest.raises(GutenbergFormatError, match="both wrapper markers"):
        parse_journal_entries(text)
