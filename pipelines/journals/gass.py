from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date, timedelta

from pipelines.journals.authors import get_author
from pipelines.journals.gutenberg import normalize_newlines
from sourcecut_api.models import JournalEntry

SOURCE_ID = "archive-gasssjournalofle00gass"
SOURCE_URL = "https://archive.org/details/gasssjournalofle00gass"
DOWNLOAD_URL = (
    "https://archive.org/download/gasssjournalofle00gass/"
    "gasssjournalofle00gass_djvu.txt"
)
PARSER_VERSION = "gass-hosmer-1904-ocr-heading-v1"

WEEKDAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|Sept|October|November|December"
)
HEADING = re.compile(
    rf"^(?P<heading>(?:ON\s+)?(?P<weekday>{WEEKDAYS})\s+"
    rf"(?:the\s+)?(?P<ordinal>\S{{1,6}}?(?:\s+st)?)\s*"
    rf"(?:of\s+)?(?:(?P<month>{MONTHS})\.?,?\s+(?P<year>180[4-6]))?[.,])",
    re.IGNORECASE | re.MULTILINE,
)
INDEX_MARKER = re.compile(r"^INDEX\s*$", re.MULTILINE)


class GassFormatError(ValueError):
    pass


def parse_gass_entries(source_text: str) -> tuple[JournalEntry, ...]:
    content = normalize_newlines(source_text)
    index = INDEX_MARKER.search(content)
    if index is not None:
        content = content[: index.start()]
    headings = tuple(HEADING.finditer(content))
    first = next(
        (
            i
            for i, match in enumerate(headings)
            if match.group("heading").startswith("ON")
        ),
        None,
    )
    if first is None:
        first = next((i for i, match in enumerate(headings) if match.group("year")), None)
    if first is None:
        raise GassFormatError("No dated Gass journal heading found")
    headings = headings[first:]

    author = get_author("Gass")
    ordinals: defaultdict[str, int] = defaultdict(int)
    entries: list[JournalEntry] = []
    previous_date: date | None = None
    for index, match in enumerate(headings):
        entry_date = _entry_date(match, previous_date)
        if previous_date is not None and entry_date <= previous_date:
            raise GassFormatError(f"Non-increasing Gass heading date at {match.group('heading')}")
        if entry_date > date(1806, 9, 23):
            break
        next_start = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        raw_text = content[match.end() : next_start].strip()
        if not raw_text:
            raise GassFormatError(f"Empty Gass entry at {match.group('heading')}")
        date_key = entry_date.isoformat()
        ordinals[date_key] += 1
        ordinal = ordinals[date_key]
        heading = match.group("heading")
        entries.append(
            JournalEntry(
                entry_id=f"{SOURCE_ID}:{author.author_id}:{date_key}:{ordinal}",
                source_id=SOURCE_ID,
                author_id=author.author_id,
                author_display_name=author.display_name,
                entry_date=entry_date,
                ordinal_for_day=ordinal,
                heading=heading,
                raw_text=raw_text,
                source_url=SOURCE_URL,
                source_locator=heading,
                raw_text_sha256=hashlib.sha256(raw_text.encode()).hexdigest(),
                parser_version=PARSER_VERSION,
            )
        )
        previous_date = entry_date
    if not entries:
        raise GassFormatError("No Gass journal entries found")
    return tuple(entries)


def _entry_date(match: re.Match[str], previous: date | None) -> date:
    weekday = _weekday(match.group("weekday"))
    month_name = match.group("month")
    year_text = match.group("year")
    if month_name and year_text:
        month = _month(month_name)
        year = int(year_text)
        digits = re.search(r"\d+", match.group("ordinal"))
        if digits is not None:
            # The printed day ordinal is the authority; the weekday is only a
            # consistency check. Scanning for "next matching weekday" instead
            # would silently misdate any entry that follows a gap of seven or
            # more days.
            try:
                candidate = date(year, month, int(digits.group()))
            except ValueError as error:
                raise GassFormatError(
                    f"Unreadable day ordinal in Gass heading {match.group('heading')}"
                ) from error
            if candidate.weekday() != weekday:
                raise GassFormatError(
                    f"Gass heading weekday does not match its printed date: "
                    f"{match.group('heading')}"
                )
            return candidate
        if previous is None:
            raise GassFormatError("First Gass heading has no readable date")
        for day in range(1, 32):
            try:
                candidate = date(year, month, day)
            except ValueError:
                break
            if candidate > previous and candidate.weekday() == weekday:
                if (candidate - previous).days >= 7:
                    raise GassFormatError(
                        "Ambiguous Gass heading without a readable ordinal after a "
                        f"gap of a week or more: {match.group('heading')}"
                    )
                return candidate
        raise GassFormatError(f"Could not resolve dated heading {match.group('heading')}")
    if previous is None:
        raise GassFormatError("Gass excerpt must begin with a month and year heading")
    for offset in range(1, 8):
        candidate = previous + timedelta(days=offset)
        if candidate.weekday() == weekday:
            return candidate
    raise AssertionError("weekday resolution exhausted")


def _weekday(value: str) -> int:
    return ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday").index(
        value.casefold()
    )


def _month(value: str) -> int:
    normalized = "september" if value.casefold() == "sept" else value.casefold()
    return (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ).index(normalized) + 1


parse = parse_gass_entries
