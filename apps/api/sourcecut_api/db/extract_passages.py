from __future__ import annotations

import argparse
from datetime import date

from pipelines.extraction import create_extractor, validate_evidence
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.models import Passage
from sourcecut_api.repositories import ClickHouseCorpusRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and validate a bounded passage window")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must not precede --start-date")
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")

    client = get_clickhouse_client()
    repository = ClickHouseCorpusRepository(client)
    extractor = create_extractor()
    inserted = 0
    failures = 0
    try:
        result = client.query(
            """
SELECT passage_id, entry_id, source_id, author_id, author_display_name, entry_date,
       passage_index, char_start, char_end, passage_text, passage_sha256
FROM passages FINAL
WHERE source_id = {source_id:String}
  AND entry_date BETWEEN {start_date:Int32} AND {end_date:Int32}
ORDER BY entry_date, passage_index
LIMIT {limit:UInt16}
""".strip(),
            parameters={
                "source_id": args.source_id,
                "start_date": _date_key(args.start_date),
                "end_date": _date_key(args.end_date),
                "limit": args.limit,
            },
        )
        passages = tuple(_passage(row) for row in result.result_rows)
        for passage in passages:
            extraction = extractor.extract(passage)
            validation = validate_evidence(passage, extraction.candidates)
            loaded = repository.load_extraction(passage, extraction, validation)
            inserted += loaded.observations_inserted
            failures += loaded.failures_inserted
    finally:
        client.close()
    print(
        f"Processed {len(passages)} passage(s); inserted {inserted} trusted observation(s) "
        f"and {failures} validation failure(s)."
    )


def _passage(row: tuple[object, ...]) -> Passage:
    key = int(row[5])
    return Passage(
        passage_id=str(row[0]),
        entry_id=str(row[1]),
        source_id=str(row[2]),
        author_id=str(row[3]),
        author_display_name=str(row[4]),
        entry_date=date(key // 10000, key // 100 % 100, key % 100),
        passage_index=int(row[6]),
        char_start=int(row[7]),
        char_end=int(row[8]),
        passage_text=str(row[9]),
        passage_sha256=row[10].decode() if isinstance(row[10], bytes) else str(row[10]),
    )


def _date_key(value: date) -> int:
    return value.year * 10000 + value.month * 100 + value.day
