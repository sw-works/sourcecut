from __future__ import annotations

import hashlib
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from sourcecut_api.models.classical_text import RawSourceDocument, TextUnit

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
PARSER_VERSION = "odyssey-tei-v1"
SPACE = re.compile(r"\s+")


class OdysseyTeiError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedOdysseyVersion:
    document: RawSourceDocument
    cts_version_urn: str
    language: str
    units: tuple[TextUnit, ...]
    warnings: tuple[str, ...] = ()


def parse_odyssey_tei(
    raw_content: str,
    *,
    version_id: str,
    upstream_path: str,
    upstream_revision: str,
    citation_corrections: Mapping[tuple[int, int], int] | None = None,
) -> ParsedOdysseyVersion:
    try:
        root = ET.fromstring(raw_content)
    except ET.ParseError as error:
        raise OdysseyTeiError(f"Malformed Odyssey TEI: {error}") from error
    body_version = root.find(f"./{TEI}text/{TEI}body/{TEI}div")
    if body_version is None:
        raise OdysseyTeiError("Odyssey TEI has no edition/translation body")
    cts_version_urn = body_version.attrib.get("n", "")
    language = body_version.attrib.get(XML_LANG, "")
    if not cts_version_urn.startswith("urn:cts:greekLit:tlg0012.tlg002."):
        raise OdysseyTeiError("Odyssey TEI has an unexpected CTS version URN")
    books = [
        element
        for element in body_version.findall(f"./{TEI}div")
        if element.attrib.get("subtype") == "book"
    ]
    book_numbers = [int(book.attrib.get("n", "0")) for book in books]
    if book_numbers != list(range(1, 25)):
        raise OdysseyTeiError(f"Expected Odyssey books 1–24, found {book_numbers}")

    raw_sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    document_id = f"odyssey-document:{version_id}:{raw_sha256}"
    document = RawSourceDocument(
        document_id=document_id,
        version_id=version_id,
        raw_content=raw_content,
        raw_sha256=raw_sha256,
        upstream_path=upstream_path,
        upstream_revision=upstream_revision,
    )
    corrections = citation_corrections or {}
    units: list[TextUnit] = []
    warnings: list[str] = []
    for book_number, book in zip(book_numbers, books, strict=True):
        book_units = (
            _parse_verse_book(book, version_id, cts_version_urn, document_id, corrections)
            if book.findall(f".//{TEI}l")
            else _parse_prose_book(
                book, version_id, cts_version_urn, document_id, corrections
            )
        )
        if not book_units:
            raise OdysseyTeiError(f"Book {book_number} contains no citable text")
        units.extend(book_units)
    for unit in units:
        if unit.citation_correction:
            warnings.append(unit.citation_correction)
    warnings.extend(_validate_units(units))
    units.sort(key=lambda unit: (unit.book, unit.line_start, unit.unit_index))
    return ParsedOdysseyVersion(
        document=document,
        cts_version_urn=cts_version_urn,
        language=language,
        units=tuple(units),
        warnings=tuple(warnings),
    )


def parse_odyssey_tei_file(
    path: Path,
    *,
    version_id: str,
    upstream_path: str,
    upstream_revision: str,
) -> ParsedOdysseyVersion:
    return parse_odyssey_tei(
        path.read_text(encoding="utf-8"),
        version_id=version_id,
        upstream_path=upstream_path,
        upstream_revision=upstream_revision,
    )


def _parse_verse_book(
    book: ET.Element,
    version_id: str,
    cts_version_urn: str,
    document_id: str,
    citation_corrections: Mapping[tuple[int, int], int],
) -> list[TextUnit]:
    book_number = int(book.attrib["n"])
    units: list[TextUnit] = []
    for index, line in enumerate(book.findall(f".//{TEI}l")):
        source_line_number = int(line.attrib.get("n", "0"))
        line_number = citation_corrections.get(
            (book_number, index), source_line_number
        )
        text = _clean_text("".join(line.itertext()))
        if not text:
            raise OdysseyTeiError(f"Empty Greek line at {book_number}.{line_number}")
        units.append(
            _text_unit(
                version_id=version_id,
                cts_version_urn=cts_version_urn,
                document_id=document_id,
                book=book_number,
                line_start=line_number,
                line_end=line_number,
                source_line_start=source_line_number,
                source_line_end=source_line_number,
                unit_index=index,
                text=text,
            )
        )
    return units


def _parse_prose_book(
    book: ET.Element,
    version_id: str,
    cts_version_urn: str,
    document_id: str,
    citation_corrections: Mapping[tuple[int, int], int],
) -> list[TextUnit]:
    book_number = int(book.attrib["n"])
    segments: list[tuple[int, str]] = []
    current_line: int | None = None
    current_text: list[str] = []
    for kind, value in _walk_text_and_milestones(book):
        if kind == "line":
            if current_line is not None:
                text = _clean_text("".join(current_text))
                if text:
                    segments.append((current_line, text))
            current_line = int(value)
            current_text = []
        elif current_line is not None:
            current_text.append(value)
    if current_line is not None:
        text = _clean_text("".join(current_text))
        if text:
            segments.append((current_line, text))

    units: list[TextUnit] = []
    canonical_starts = [
        citation_corrections.get((book_number, index), line_start)
        for index, (line_start, _) in enumerate(segments)
    ]
    for index, (source_line_start, text) in enumerate(segments):
        line_start = canonical_starts[index]
        next_start = (
            canonical_starts[index + 1]
            if index + 1 < len(canonical_starts)
            else line_start + 1
        )
        next_source_start = (
            segments[index + 1][0]
            if index + 1 < len(segments)
            else source_line_start + 1
        )
        units.append(
            _text_unit(
                version_id=version_id,
                cts_version_urn=cts_version_urn,
                document_id=document_id,
                book=book_number,
                line_start=line_start,
                line_end=max(line_start, next_start - 1),
                source_line_start=source_line_start,
                source_line_end=max(source_line_start, next_source_start - 1),
                unit_index=index,
                text=text,
            )
        )
    return units


def _walk_text_and_milestones(element: ET.Element) -> Iterator[tuple[str, str]]:
    if element.text:
        yield ("text", element.text)
    for child in element:
        if child.tag == f"{TEI}milestone" and child.attrib.get("unit") == "line":
            number = child.attrib.get("n")
            if number and number.isdigit():
                yield ("line", number)
        else:
            yield from _walk_text_and_milestones(child)
        if child.tail:
            yield ("text", child.tail)


def _text_unit(
    *,
    version_id: str,
    cts_version_urn: str,
    document_id: str,
    book: int,
    line_start: int,
    line_end: int,
    source_line_start: int,
    source_line_end: int,
    unit_index: int,
    text: str,
) -> TextUnit:
    citation = _citation(book, line_start, line_end)
    range_ref = f"{book}.{line_start}"
    if line_end != line_start:
        range_ref += f"-{book}.{line_end}"
    return TextUnit(
        text_unit_id=f"text-unit:{version_id}:{book}:{line_start}-{line_end}",
        version_id=version_id,
        book=book,
        line_start=line_start,
        line_end=line_end,
        source_line_start=source_line_start,
        source_line_end=source_line_end,
        citation_correction=(
            f"Applied manifest citation correction for {version_id} book {book} unit "
            f"{unit_index}: source {source_line_start} to canonical {line_start}"
            if source_line_start != line_start
            else ""
        ),
        citation=citation,
        cts_urn=f"{cts_version_urn}:{range_ref}",
        unit_index=unit_index,
        original_text=text,
        normalized_text=unicodedata.normalize("NFC", text),
        source_document_id=document_id,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        parser_version=PARSER_VERSION,
    )


def _citation(book: int, line_start: int, line_end: int) -> str:
    suffix = str(line_start) if line_end == line_start else f"{line_start}–{line_end}"
    return f"Od. {book}.{suffix}"


def _clean_text(value: str) -> str:
    return SPACE.sub(" ", value).strip()


def _validate_units(units: list[TextUnit]) -> tuple[str, ...]:
    seen: set[tuple[str, int, int]] = set()
    previous: dict[tuple[str, int], int] = {}
    warnings: list[str] = []
    for unit in units:
        key = (unit.version_id, unit.book, unit.line_start)
        if key in seen:
            raise OdysseyTeiError(f"Duplicate citable unit: {unit.cts_urn}")
        seen.add(key)
        book_key = (unit.version_id, unit.book)
        if unit.line_start <= previous.get(book_key, 0):
            warnings.append(f"Upstream non-monotonic line marker at {unit.cts_urn}")
        if unit.line_end < unit.line_start:
            raise OdysseyTeiError(f"Invalid line range at {unit.cts_urn}")
        previous[book_key] = unit.line_start
    return tuple(warnings)
