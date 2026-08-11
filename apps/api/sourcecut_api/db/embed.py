from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pipelines.embeddings import EmbeddingSettings, create_embedder
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.telemetry import telemetry_span

INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}


class Embedder(Protocol):
    settings: EmbeddingSettings

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingBackfillResult:
    passages_embedded: int
    media_assets_embedded: int


class EmbeddingBackfillService:
    def __init__(self, client: Any, embedder: Embedder, *, batch_size: int = 64) -> None:
        self._client = client
        self._embedder = embedder
        self._batch_size = batch_size

    def run(self) -> EmbeddingBackfillResult:
        return EmbeddingBackfillResult(
            passages_embedded=self._backfill("passages"),
            media_assets_embedded=self._backfill("media_assets"),
        )

    def _backfill(self, table: str) -> int:
        embedded = 0
        while True:
            selection = (
                "* EXCEPT(ingested_at, raw_metadata), "
                "toJSONString(raw_metadata) AS raw_metadata"
                if table == "media_assets"
                else "* EXCEPT(ingested_at)"
            )
            result = self._client.query(
                f"""
SELECT {selection}
FROM {table} FINAL
WHERE embedding_model != {{model:String}}
ORDER BY {"passage_id" if table == "passages" else "asset_id"}
LIMIT {{limit:UInt16}}
""".strip(),
                parameters={
                    "model": self._embedder.settings.model,
                    "limit": self._batch_size,
                },
            )
            rows = [list(row) for row in result.result_rows]
            if not rows:
                return embedded
            columns = list(result.column_names)
            if table == "media_assets":
                raw_index = columns.index("raw_metadata")
                for row in rows:
                    row[raw_index] = json.loads(str(row[raw_index]))
            texts = [_embedding_text(table, columns, row) for row in rows]
            with telemetry_span(
                "sourcecut.embedding.batch",
                {
                    "sourcecut.embedding.table": table,
                    "sourcecut.embedding.model": self._embedder.settings.model,
                    "sourcecut.embedding.rows": len(rows),
                    "sourcecut.embedding.input_characters": sum(map(len, texts)),
                },
            ):
                vectors = self._embedder.embed_documents(texts)
                for row, vector in zip(rows, vectors, strict=True):
                    row[columns.index("embedding")] = list(vector)
                    row[columns.index("embedding_model")] = self._embedder.settings.model
                self._client.insert(
                    table,
                    rows,
                    column_names=columns,
                    settings=INSERT_SETTINGS,
                )
            embedded += len(rows)


def _embedding_text(table: str, columns: list[str], row: list[Any]) -> str:
    if table == "passages":
        return str(row[columns.index("passage_text")])
    values = [
        row[columns.index("title")],
        row[columns.index("description")],
        *row[columns.index("subjects")],
    ]
    return "\n".join(str(value) for value in values if value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill SourceCut Gemini embeddings")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 256:
        parser.error("--batch-size must be between 1 and 256")
    settings = EmbeddingSettings.from_env()
    embedder = create_embedder(settings)
    client = get_clickhouse_client()
    try:
        bootstrap_database(client)
        result = EmbeddingBackfillService(
            client, embedder, batch_size=args.batch_size
        ).run()
    finally:
        client.close()
    print(
        f"Embedded {result.passages_embedded} passage(s) and "
        f"{result.media_assets_embedded} media asset(s)."
    )


if __name__ == "__main__":
    main()
