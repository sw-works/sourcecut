from __future__ import annotations

import asyncio
import os

import pytest

from pipelines.embeddings import create_embedder
from sourcecut_api.integrations.clickhouse_mcp import (
    ClickHouseMcpClient,
    ClickHouseMcpSettings,
    _query_rows,
)
from sourcecut_api.services.board import _semantic_passage_query

EXPECTED_HUNGER_PASSAGES = {
    "gutenberg-8419:clark:1805-09-18:1:passage:0",
    "gutenberg-8419:lewis:1805-09-18:1:passage:0",
}


@pytest.mark.skipif(
    os.getenv("SOURCECUT_RUN_LIVE_EMBEDDING_TESTS") != "true",
    reason="set SOURCECUT_RUN_LIVE_EMBEDDING_TESTS=true with Gemini and MCP environments",
)
def test_exhaustion_and_starvation_semantic_query_returns_known_passages() -> None:
    vector = create_embedder().embed_query("the party is exhausted and starving")
    payload = asyncio.run(
        ClickHouseMcpClient(ClickHouseMcpSettings.from_env()).call_tool(
            "run_query", {"query": _semantic_passage_query(vector)}
        )
    )
    columns, rows = _query_rows(payload)
    top_ten = {str(row[columns.index("passage_id")]) for row in rows[:10]}

    assert EXPECTED_HUNGER_PASSAGES <= top_ten
