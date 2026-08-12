from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from sourcecut_api.models import HistoricalEvidence, ObservationCategory, Passage

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

QUERY_SETTINGS = {
    "max_execution_time": 30,
    "max_rows_to_read": 1_000_000,
    "max_bytes_to_read": 100_000_000,
    "max_result_rows": 1_000,
    "result_overflow_mode": "throw",
    "timeout_before_checking_execution_speed": 0,
    "join_algorithm": "auto",
}


class ClickHouseEvidenceRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def search_observations(
        self,
        start_date: date,
        end_date: date,
        *,
        category: ObservationCategory | None = None,
        term: str | None = None,
        limit: int = 100,
    ) -> tuple[HistoricalEvidence, ...]:
        if end_date < start_date:
            raise ValueError("end_date must not be before start_date")
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")

        observation_filters = ["trusted = true", "validation_status = 'valid'"]
        parameters: dict[str, object] = {
            "start_date": _calendar_date_key(start_date),
            "end_date": _calendar_date_key(end_date),
            "limit": limit,
        }
        if category is not None:
            observation_filters.append("category = {category:String}")
            parameters["category"] = category
        if term is not None and term.strip():
            # hasToken needles must be single tokens — a term with spaces or
            # punctuation ("pack horse") makes ClickHouse raise BAD_ARGUMENTS.
            # Tokenize here and require every token in either column.
            tokens = re.findall(r"[a-z0-9]+", term.strip().casefold())
            if not tokens:
                raise ValueError("term contains no searchable tokens")
            token_filters = []
            for index, token in enumerate(tokens):
                name = f"term_{index}"
                token_filters.append(
                    f"(hasToken(lower(canonical_term), {{{name}:String}}) "
                    f"OR hasToken(lower(normalized_description), {{{name}:String}}))"
                )
                parameters[name] = token
            observation_filters.append("(" + " AND ".join(token_filters) + ")")

        query = f"""
SELECT
    o.observation_id,
    p.passage_id,
    p.entry_id,
    p.source_id,
    p.author_id,
    p.author_display_name,
    p.entry_date,
    o.category,
    o.canonical_term,
    o.normalized_description,
    o.explicit,
    o.source_quote,
    o.source_start,
    o.source_end,
    o.passage_sha256,
    o.confidence,
    p.passage_text
FROM
(
    SELECT passage_id, entry_id, source_id, author_id, author_display_name, entry_date, passage_text
    FROM passages FINAL
    WHERE entry_date BETWEEN {{start_date:Int32}} AND {{end_date:Int32}}
) AS p
ALL INNER JOIN
(
    SELECT observation_id, passage_id, category, canonical_term, normalized_description,
           explicit, source_quote, source_start, source_end, passage_sha256, confidence
    FROM observations FINAL
    WHERE {" AND ".join(observation_filters)}
) AS o ON o.passage_id = p.passage_id
ORDER BY o.canonical_term, p.author_id, p.entry_date, o.observation_id
LIMIT {{limit:UInt16}}
""".strip()
        rows = self._client.query(
            query,
            parameters=parameters,
            settings=QUERY_SETTINGS,
        ).result_rows
        return tuple(_evidence_from_row(row) for row in rows)

    def get_passage(self, passage_id: str) -> Passage | None:
        if not passage_id:
            raise ValueError("passage_id must not be empty")
        rows = self._client.query(
            """
SELECT passage_id, entry_id, source_id, author_id, author_display_name, entry_date,
       passage_index, char_start, char_end, passage_text, passage_sha256
FROM passages FINAL
WHERE passage_id = {passage_id:String}
LIMIT 2
""".strip(),
            parameters={"passage_id": passage_id},
            settings=QUERY_SETTINGS,
        ).result_rows
        if not rows:
            return None
        if len(rows) > 1:
            raise RuntimeError(f"Duplicate passage_id in ClickHouse: {passage_id}")
        row = rows[0]
        return Passage(
            passage_id=str(row[0]),
            entry_id=str(row[1]),
            source_id=str(row[2]),
            author_id=str(row[3]),
            author_display_name=str(row[4]),
            entry_date=_date_from_calendar_key(int(row[5])),
            passage_index=int(row[6]),
            char_start=int(row[7]),
            char_end=int(row[8]),
            passage_text=str(row[9]),
            passage_sha256=_hash_text(row[10]),
        )


def _evidence_from_row(row: tuple[object, ...]) -> HistoricalEvidence:
    return HistoricalEvidence(
        observation_id=str(row[0]),
        passage_id=str(row[1]),
        entry_id=str(row[2]),
        source_id=str(row[3]),
        author_id=str(row[4]),
        author_display_name=str(row[5]),
        entry_date=_date_from_calendar_key(int(row[6])),
        category=str(row[7]),
        canonical_term=str(row[8]),
        normalized_description=str(row[9]),
        explicit=bool(row[10]),
        source_quote=str(row[11]),
        source_start=int(row[12]),
        source_end=int(row[13]),
        passage_sha256=_hash_text(row[14]),
        confidence=float(row[15]),
        passage_text=str(row[16]),
    )


def _calendar_date_key(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def _date_from_calendar_key(value: int) -> date:
    year, month_day = divmod(value, 10_000)
    month, day = divmod(month_day, 100)
    return date(year, month, day)


def _hash_text(value: object) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else str(value)
