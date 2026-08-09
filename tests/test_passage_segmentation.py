from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from pipelines.journals.gutenberg import parse_journal_entries, read_gutenberg_text
from pipelines.journals.passages import segment_entries, segment_entry
from sourcecut_api.models import JournalEntry

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "journals"
    / "gutenberg_8419_september_21_1805.txt"
)


def make_entry(raw_text: str, entry_id: str = "test:lewis:1805-09-21:1") -> JournalEntry:
    return JournalEntry(
        entry_id=entry_id,
        source_id="test",
        author_id="lewis",
        author_display_name="Meriwether Lewis",
        entry_date=date(1805, 9, 21),
        ordinal_for_day=1,
        heading="[Lewis, September 21, 1805]",
        raw_text=raw_text,
        source_url="https://example.test/source",
        source_locator="fixture",
        raw_text_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        parser_version="test-v1",
    )


def assert_exact_reconstruction(entry: JournalEntry) -> None:
    passages = segment_entry(entry)

    assert passages[0].char_start == 0
    assert passages[-1].char_end == len(entry.raw_text)
    assert "".join(passage.passage_text for passage in passages) == entry.raw_text
    for index, passage in enumerate(passages):
        assert passage.entry_id == entry.entry_id
        assert passage.author_id == entry.author_id
        assert passage.entry_date == entry.entry_date
        assert passage.passage_index == index
        assert entry.raw_text[passage.char_start : passage.char_end] == passage.passage_text
        assert passage.passage_sha256 == hashlib.sha256(
            passage.passage_text.encode("utf-8")
        ).hexdigest()
        if index:
            assert passages[index - 1].char_end == passage.char_start


def test_short_entry_is_one_exact_passage() -> None:
    entry = make_entry("An exact short entry.\nWith its original line breaks.")

    passages = segment_entry(entry)

    assert len(passages) == 1
    assert passages[0].passage_id == f"{entry.entry_id}:passage:0"
    assert_exact_reconstruction(entry)


def test_long_entry_splits_at_paragraph_boundaries() -> None:
    raw_text = "A" * 3_700 + "\n\n" + "B" * 3_800 + "\n\n" + "C" * 3_000
    entry = make_entry(raw_text)

    passages = segment_entry(entry)

    assert [len(passage.passage_text) for passage in passages] == [3_702, 3_802, 3_000]
    assert passages[0].passage_text.endswith("\n\n")
    assert passages[1].passage_text.endswith("\n\n")
    assert_exact_reconstruction(entry)


def test_single_long_paragraph_uses_deterministic_fallback() -> None:
    entry = make_entry("A" * 12_345)

    first = segment_entry(entry)
    second = segment_entry(entry)

    assert [len(passage.passage_text) for passage in first] == [5_000, 5_000, 2_345]
    assert first == second
    assert_exact_reconstruction(entry)


def test_entries_never_share_passages() -> None:
    first = make_entry("A" * 6_001, "test:lewis:1805-09-21:1")
    second = make_entry("B" * 6_001, "test:lewis:1805-09-22:1").model_copy(
        update={"entry_date": date(1805, 9, 22)}
    )

    passages = segment_entries((first, second))

    assert {passage.entry_id for passage in passages[:2]} == {first.entry_id}
    assert {passage.entry_id for passage in passages[2:]} == {second.entry_id}
    assert all("B" not in passage.passage_text for passage in passages[:2])
    assert all("A" not in passage.passage_text for passage in passages[2:])
    assert_exact_reconstruction(first)
    assert_exact_reconstruction(second)


def test_authentic_fixture_entries_reconstruct_exactly() -> None:
    entries = parse_journal_entries(read_gutenberg_text(FIXTURE))

    for entry in entries:
        assert_exact_reconstruction(entry)
