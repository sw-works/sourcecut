from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from sourcecut_api.models import JournalEntry

GUTENBERG_EBOOK_ID = 8419
SOURCE_ID = "gutenberg-8419"
SOURCE_URL = "https://www.gutenberg.org/ebooks/8419"
DOWNLOAD_URL = "https://www.gutenberg.org/cache/epub/8419/pg8419.txt"
PARSER_VERSION = "gutenberg-heading-v1"

START_MARKER = re.compile(
    r"^\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*$",
    re.IGNORECASE | re.MULTILINE,
)
END_MARKER = re.compile(
    r"^\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*$",
    re.IGNORECASE | re.MULTILINE,
)
HEADING = re.compile(
    r"^\[(?P<author>[A-Za-z]+), (?P<month>[A-Za-z]+) "
    r"(?P<day>[0-9]{1,2}), (?P<year>180[3-6])\]$",
    re.MULTILINE,
)
SUPPORTED_AUTHORS = {
    "Lewis": ("lewis", "Meriwether Lewis"),
    "Clark": ("clark", "William Clark"),
}


class GutenbergFormatError(ValueError):
    pass


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_gutenberg_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig")


def download_gutenberg_text(url: str = DOWNLOAD_URL, timeout_seconds: float = 30.0) -> str:
    request = Request(url, headers={"User-Agent": "SourceCut/0.1 Gutenberg corpus ingestion"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8-sig")


def strip_gutenberg_wrapper(text: str) -> str:
    normalized = normalize_newlines(text)
    start = START_MARKER.search(normalized)
    end = END_MARKER.search(normalized)
    if (start is None) != (end is None):
        raise GutenbergFormatError("Gutenberg text must contain both wrapper markers or neither")
    if start is None or end is None:
        return normalized.strip("\n")
    if end.start() <= start.end():
        raise GutenbergFormatError("Gutenberg end marker appears before the start marker")
    return normalized[start.end() : end.start()].strip("\n")


def parse_journal_entries(text: str) -> tuple[JournalEntry, ...]:
    content = strip_gutenberg_wrapper(text)
    headings = tuple(HEADING.finditer(content))
    if not headings:
        raise GutenbergFormatError("No journal entry headings found")

    ordinals: defaultdict[tuple[str, str], int] = defaultdict(int)
    entries: list[JournalEntry] = []

    for index, match in enumerate(headings):
        author = match.group("author")
        author_details = SUPPORTED_AUTHORS.get(author)
        if author_details is None:
            continue

        next_start = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        raw_text = content[match.end() : next_start].strip("\n")
        entry_date = datetime.strptime(
            f"{match.group('month')} {match.group('day')} {match.group('year')}",
            "%B %d %Y",
        ).date()
        author_id, author_display_name = author_details
        ordinal_key = (author_id, entry_date.isoformat())
        ordinals[ordinal_key] += 1
        ordinal = ordinals[ordinal_key]
        heading = match.group(0)

        entries.append(
            JournalEntry(
                entry_id=f"{SOURCE_ID}:{author_id}:{entry_date.isoformat()}:{ordinal}",
                source_id=SOURCE_ID,
                author_id=author_id,
                author_display_name=author_display_name,
                entry_date=entry_date,
                ordinal_for_day=ordinal,
                heading=heading,
                raw_text=raw_text,
                source_url=SOURCE_URL,
                source_locator=heading,
                raw_text_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
                parser_version=PARSER_VERSION,
            )
        )

    if not entries:
        raise GutenbergFormatError("No Lewis or Clark journal entries found")
    return tuple(entries)


def serialize_entries(entries: tuple[JournalEntry, ...]) -> bytes:
    payload = [entry.model_dump(mode="json") for entry in entries]
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
