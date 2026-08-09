from __future__ import annotations

import hashlib
import re

from sourcecut_api.models import JournalEntry, Passage

SINGLE_PASSAGE_LIMIT = 6_000
MIN_SPLIT_SIZE = 3_500
MAX_SPLIT_SIZE = 5_000

PARAGRAPH_BOUNDARY = re.compile(r"\n[ \t]*\n+")


def segment_entry(entry: JournalEntry) -> tuple[Passage, ...]:
    if not entry.raw_text:
        raise ValueError(f"Cannot segment empty journal entry {entry.entry_id}")

    boundaries = tuple(match.end() for match in PARAGRAPH_BOUNDARY.finditer(entry.raw_text))
    spans: list[tuple[int, int]] = []
    char_start = 0

    while len(entry.raw_text) - char_start > SINGLE_PASSAGE_LIMIT:
        window_start = char_start + MIN_SPLIT_SIZE
        window_end = char_start + MAX_SPLIT_SIZE
        candidates = [boundary for boundary in boundaries if window_start <= boundary <= window_end]
        char_end = candidates[-1] if candidates else window_end
        spans.append((char_start, char_end))
        char_start = char_end

    spans.append((char_start, len(entry.raw_text)))

    return tuple(
        _build_passage(entry, passage_index, char_start, char_end)
        for passage_index, (char_start, char_end) in enumerate(spans)
    )


def segment_entries(entries: tuple[JournalEntry, ...]) -> tuple[Passage, ...]:
    return tuple(passage for entry in entries for passage in segment_entry(entry))


def _build_passage(
    entry: JournalEntry,
    passage_index: int,
    char_start: int,
    char_end: int,
) -> Passage:
    passage_text = entry.raw_text[char_start:char_end]
    return Passage(
        passage_id=f"{entry.entry_id}:passage:{passage_index}",
        entry_id=entry.entry_id,
        source_id=entry.source_id,
        author_id=entry.author_id,
        author_display_name=entry.author_display_name,
        entry_date=entry.entry_date,
        passage_index=passage_index,
        char_start=char_start,
        char_end=char_end,
        passage_text=passage_text,
        passage_sha256=hashlib.sha256(passage_text.encode("utf-8")).hexdigest(),
    )
