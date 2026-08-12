from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence

from sourcecut_api.models.classical_text import ClassicalPassage, TextUnit

SEGMENTATION_VERSION = "odyssey-passage-v1"


def build_classical_passages(
    units: Sequence[TextUnit], *, window_size: int = 20, overlap: int = 5
) -> tuple[ClassicalPassage, ...]:
    if window_size < 1 or not 0 <= overlap < window_size:
        raise ValueError("Passage window must be positive with smaller non-negative overlap")
    grouped: dict[tuple[str, int], list[TextUnit]] = defaultdict(list)
    for unit in units:
        grouped[(unit.version_id, unit.book)].append(unit)
    passages: list[ClassicalPassage] = []
    step = window_size - overlap
    for (version_id, book), book_units in sorted(grouped.items()):
        ordered = sorted(book_units, key=lambda item: (item.line_start, item.unit_index))
        for start in range(0, len(ordered), step):
            window = ordered[start : start + window_size]
            if not window:
                continue
            text = "\n".join(unit.original_text for unit in window)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            passages.append(
                ClassicalPassage(
                    passage_id=(
                        f"classical-passage:{version_id}:{book}:"
                        f"{window[0].line_start}-{window[-1].line_end}:{digest[:16]}"
                    ),
                    version_id=version_id,
                    book=book,
                    line_start=window[0].line_start,
                    line_end=window[-1].line_end,
                    unit_ids=tuple(unit.text_unit_id for unit in window),
                    passage_text=text,
                    passage_sha256=digest,
                    segmentation_version=SEGMENTATION_VERSION,
                )
            )
            if start + window_size >= len(ordered):
                break
    return tuple(passages)
