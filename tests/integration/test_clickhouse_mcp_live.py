from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.integrations.clickhouse_mcp import (
    ClickHouseMcpClient,
    ClickHouseMcpSettings,
    _query_rows,
    run_mcp_preflight,
)


@pytest.mark.skipif(
    os.getenv("SOURCECUT_RUN_LIVE_MCP_TESTS") != "true",
    reason="set SOURCECUT_RUN_LIVE_MCP_TESTS=true with the MCP environment",
)
def test_official_mcp_reaches_live_sourcecut_cluster_read_only_and_authenticated() -> None:
    result = asyncio.run(run_mcp_preflight())

    assert {"list_databases", "list_tables", "run_query"} <= set(result.adk_tools)
    assert result.sourcecut_tables_reached
    assert result.parameterized_views_reached
    assert result.vector_query_reached
    assert result.term_dictionary_reached
    assert result.passage_count > 0
    assert result.visual_evidence_authors >= 2
    assert result.wagon_mentions == 0
    assert result.deterministic_snow_lookup
    assert result.read_only_enforced
    assert result.unauthenticated_status in {401, 403}


@pytest.mark.skipif(
    os.getenv("SOURCECUT_RUN_LIVE_POLICY_TESTS") != "true",
    reason="set SOURCECUT_RUN_LIVE_POLICY_TESTS=true with admin and MCP environments",
)
def test_mcp_role_cannot_read_invalid_observation_visible_to_admin() -> None:
    admin = get_clickhouse_client()
    passage = admin.query(
        """
SELECT passage_id, entry_id, source_id, passage_sha256
FROM sourcecut.passages FINAL
ORDER BY passage_id
LIMIT 1
"""
    ).result_rows[0]
    observation_id = f"policy-probe:{uuid4()}"
    admin.insert(
        "sourcecut.observations",
        [[
            observation_id,
            "policy-probe",
            passage[0],
            passage[1],
            passage[2],
            "test",
            "invalid-probe",
            "invalid policy probe",
            False,
            "probe",
            0,
            5,
            passage[3],
            0.0,
            "test",
            "1",
            "policy-probe",
            False,
            "invalid",
        ]],
        column_names=[
            "observation_id",
            "extraction_run_id",
            "passage_id",
            "entry_id",
            "source_id",
            "category",
            "canonical_term",
            "normalized_description",
            "explicit",
            "source_quote",
            "source_start",
            "source_end",
            "passage_sha256",
            "confidence",
            "model",
            "schema_version",
            "prompt_version",
            "trusted",
            "validation_status",
        ],
    )

    async def runtime_count() -> int:
        payload = await ClickHouseMcpClient(
            ClickHouseMcpSettings.from_env()
        ).call_tool(
            "run_query",
            {
                "query": (
                    "SELECT count() AS rows FROM sourcecut.observations FINAL "
                    f"WHERE observation_id = '{observation_id}' LIMIT 1"
                )
            },
        )
        columns, rows = _query_rows(payload)
        return int(rows[0][columns.index("rows")])

    try:
        assert admin.query(
            "SELECT count() FROM sourcecut.observations "
            f"WHERE observation_id = '{observation_id}'"
        ).result_rows[0][0] == 1
        assert asyncio.run(runtime_count()) == 0
    finally:
        admin.command(
            "DELETE FROM sourcecut.observations "
            f"WHERE observation_id = '{observation_id}'"
        )
