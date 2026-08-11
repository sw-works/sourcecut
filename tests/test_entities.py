from __future__ import annotations

import json
from pathlib import Path

from sourcecut_api.db.load_entities import extract_exact_mentions, validate_mention


def test_exact_entity_mentions_have_stable_valid_spans() -> None:
    entities = json.loads(
        Path("data/reference/entities.json").read_text(encoding="utf-8")
    )
    passage = {
        "passage_id": "passage-1",
        "entry_date": 18050911,
        "author_id": "clark",
        "passage_text": "The Flathead guides had two horses.",
    }

    first = extract_exact_mentions(passage, entities)
    second = extract_exact_mentions(passage, entities)

    assert [row[0] for row in first] == [row[0] for row in second]
    assert {row[1] for row in first} == {"salish-flathead", "horses"}
    assert all(row[8] is True and row[9] == "valid" for row in first)
    for row in first:
        assert passage["passage_text"][row[6] : row[7]] == row[5]


def test_corrupted_entity_mention_offset_is_rejected() -> None:
    text = "The Flathead guides arrived."

    assert validate_mention(text, "Flathead", 4, 12)
    assert not validate_mention(text, "Flathead", 5, 13)
