from __future__ import annotations

import asyncio
import os

import pytest

from sourcecut_api.integrations.clickhouse_mcp import run_mcp_preflight


@pytest.mark.skipif(
    os.getenv("SOURCECUT_RUN_LIVE_MCP_TESTS") != "true",
    reason="set SOURCECUT_RUN_LIVE_MCP_TESTS=true with the MCP environment",
)
def test_official_mcp_reaches_live_sourcecut_cluster_read_only_and_authenticated() -> None:
    result = asyncio.run(run_mcp_preflight())

    assert {"list_databases", "list_tables", "run_query"} <= set(result.adk_tools)
    assert result.sourcecut_tables_reached
    assert result.passage_count > 0
    assert result.visual_evidence_authors >= 2
    assert result.wagon_mentions == 0
    assert result.deterministic_snow_lookup
    assert result.read_only_enforced
    assert result.unauthenticated_status in {401, 403}
