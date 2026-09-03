"""Retrieval-vocabulary memory.

When a coverage round widens a search and that wider vocabulary actually
returns passages, the terms are written back so later sessions start with
them. This is curated reference data (ADR-017): it steers retrieval and is
never displayed as a historical claim. Rows written here are marked
``provenance='discovered'`` so a curator can tell them from hand-written
vocabulary and reverse them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}
DISCOVERED = "discovered"


class TermExpansionRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def record_discovered_terms(
        self, category: str, term: str, expansions: Sequence[str]
    ) -> None:
        """Merge newly useful expansions into one (category, term) row.

        ReplacingMergeTree keyed on (category, term) means the newest row
        wins, so the merged set is read back rather than accumulating
        duplicates. Curated rows are never downgraded: a row that already
        exists keeps its notes and only gains terms.
        """
        additions = tuple(
            dict.fromkeys(
                str(value).casefold().strip()
                for value in expansions
                if str(value).strip()
            )
        )
        if not category or not term or not additions:
            return
        existing, provenance, notes = self._existing(category, term)
        merged = tuple(dict.fromkeys((*existing, *additions)))
        if merged == existing:
            return
        self._client.insert(
            "term_expansions",
            [
                [
                    category,
                    term,
                    list(merged),
                    notes,
                    provenance or DISCOVERED,
                    datetime.now(UTC),
                ]
            ],
            column_names=[
                "category",
                "term",
                "expansions",
                "notes",
                "provenance",
                "updated_at",
            ],
            settings=INSERT_SETTINGS,
        )

    def _existing(self, category: str, term: str) -> tuple[tuple[str, ...], str, str]:
        rows = self._client.query(
            "SELECT expansions, provenance, notes FROM term_expansions FINAL "
            "WHERE category = {category:String} AND term = {term:String} LIMIT 1",
            parameters={"category": category, "term": term},
        ).result_rows
        if not rows:
            return (), DISCOVERED, "Discovered by a research coverage round."
        expansions, provenance, notes = rows[0]
        return (
            tuple(str(value) for value in expansions),
            str(provenance) or DISCOVERED,
            str(notes),
        )
