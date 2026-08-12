from __future__ import annotations

import base64
import json
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from sourcecut_api.models.linguistic import (
    FormulaResult,
    SavedSearch,
    SavedSearchCreate,
    SearchMode,
    TextMatchSpan,
    TextSearchHit,
    TextSearchRequest,
    TextSearchResponse,
    TokenAnalysis,
)


class SearchCursorError(ValueError):
    pass


def decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, UnicodeDecodeError) as error:
        raise SearchCursorError("Invalid search cursor") from error
    if value < 0 or value > 100_000:
        raise SearchCursorError("Search cursor is outside the allowed range")
    return value


def build_search_response(
    request: TextSearchRequest,
    rows: list[dict[str, object]],
    offset: int,
) -> TextSearchResponse:
    has_more = len(rows) > request.page_size
    page = rows[: request.page_size]
    hits = tuple(_search_hit(request, row) for row in page)
    books = Counter(str(hit.book) for hit in hits)
    versions = Counter(hit.version_id for hit in hits)
    warnings = []
    if request.mode in {SearchMode.LEMMA, SearchMode.FORM, SearchMode.NORMALIZED}:
        warnings.append(
            "Lemma and morphology fields are derived annotations aligned from the Perseus "
            "Ancient Greek Dependency Treebank and are not primary textual evidence."
        )
    return TextSearchResponse(
        query=request.query,
        mode=request.mode,
        interpretation=_interpretation(request),
        hits=hits,
        facets={"book": dict(books), "version": dict(versions)},
        next_cursor=_encode_cursor(offset + request.page_size) if has_more else None,
        warnings=tuple(warnings),
    )


def build_formula_results(rows: list[dict[str, object]]) -> tuple[FormulaResult, ...]:
    results = []
    for row in rows:
        occurrences = []
        for item in row.get("occurrences", []) or []:
            if isinstance(item, dict):
                occurrences.append(item)
            else:
                values = list(item)
                occurrences.append(
                    {
                        "book": int(values[0]),
                        "line_start": int(values[1]),
                        "line_end": int(values[2]),
                        "occurrence_id": str(values[3]),
                    }
                )
        results.append(
            FormulaResult(
                formula_id=str(row["formula_id"]),
                display_formula=str(row["display_formula"]),
                normalized_formula=str(row["normalized_formula"]),
                ngram_size=int(row["ngram_size"]),
                occurrence_count=int(row["occurrence_count"]),
                occurrences=tuple(occurrences),
            )
        )
    return tuple(results)


class MemorySavedSearchStore:
    def __init__(self) -> None:
        self._items: dict[str, SavedSearch] = {}

    def create(self, request: SavedSearchCreate, owner_id: str = "local-preview") -> SavedSearch:
        item = SavedSearch(
            saved_search_id=f"saved-search:{uuid4()}",
            owner_id=owner_id,
            name=request.name,
            search=request.search,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._items[item.saved_search_id] = item
        return item

    def list(self, owner_id: str = "local-preview") -> tuple[SavedSearch, ...]:
        return tuple(item for item in self._items.values() if item.owner_id == owner_id)

    def delete(self, saved_search_id: str, owner_id: str = "local-preview") -> bool:
        item = self._items.get(saved_search_id)
        if item is None or item.owner_id != owner_id:
            return False
        del self._items[saved_search_id]
        return True


def _search_hit(request: TextSearchRequest, row: dict[str, object]) -> TextSearchHit:
    text = str(row["original_text"])
    token = None
    if "token_id" in row:
        start = int(row["char_start"])
        end = int(row["char_end"])
        matches = (TextMatchSpan(char_start=start, char_end=end, token_id=str(row["token_id"])),)
        token = TokenAnalysis(
            token_id=str(row["token_id"]),
            surface=str(row["surface"]),
            lemma=str(row.get("lemma", "")),
            part_of_speech=str(row.get("part_of_speech", "unknown")),
            morphology=_json_object(row.get("morphology", {})),
            annotation_source=str(row.get("annotation_source", "")),
            annotation_version=str(row.get("annotation_version", "")),
            annotation_confidence=float(row.get("annotation_confidence", 0)),
            review_status=str(row.get("review_status", "unreviewed")),
        )
    else:
        matches = tuple(_find_matches(text, request.query, request.mode == SearchMode.ENGLISH))
    return TextSearchHit(
        text_unit_id=str(row["text_unit_id"]),
        version_id=str(row["version_id"]),
        citation=str(row["citation"]),
        cts_urn=str(row["cts_urn"]),
        book=int(row["book"]),
        line_start=int(row["line_start"]),
        line_end=int(row["line_end"]),
        text=text,
        matches=matches,
        token=token,
    )


def _find_matches(text: str, query: str, case_insensitive: bool) -> list[TextMatchSpan]:
    haystack = text.casefold() if case_insensitive else text
    needle = query.casefold() if case_insensitive else query
    matches = []
    start = 0
    while needle and (position := haystack.find(needle, start)) >= 0:
        matches.append(TextMatchSpan(char_start=position, char_end=position + len(needle)))
        start = position + len(needle)
    return matches


def _json_object(value: object) -> dict[str, str]:
    if isinstance(value, str):
        parsed = json.loads(value)
        return {str(key): str(item) for key, item in parsed.items()}
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    return {}


def _interpretation(request: TextSearchRequest) -> str:
    labels = {
        SearchMode.EXACT: "Exact Unicode substring in the selected source versions.",
        SearchMode.ENGLISH: "Case-insensitive wording in identified English translations.",
        SearchMode.LEMMA: "Accent-insensitive imported treebank lemma.",
        SearchMode.FORM: "Accent-insensitive Greek token form.",
        SearchMode.NORMALIZED: (
            "Accent-insensitive Greek token form; displayed text remains unchanged."
        ),
    }
    return labels[request.mode]


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()
