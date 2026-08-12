from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.main import DEFAULT_PROMPT, create_app


@pytest.mark.skipif(
    os.getenv("SOURCECUT_RUN_LIVE_SESSION_TESTS") != "true",
    reason="set SOURCECUT_RUN_LIVE_SESSION_TESTS=true with admin and MCP environments",
)
def test_session_survives_app_restart_and_rolls_up_real_mcp_events() -> None:
    with TestClient(create_app()) as first:
        started = first.post(
            "/api/research",
            json={"query": DEFAULT_PROMPT, "public_domain_only": True},
        ).json()
        session_id = started["session_id"]
        for _ in range(200):
            result = first.get(f"/api/research/{session_id}").json()
            if result["status"] in {"complete", "failed"}:
                break
            time.sleep(0.05)

    assert result["status"] == "complete"
    with TestClient(create_app()) as restarted:
        restored = restarted.get(f"/api/research/{session_id}").json()
        with restarted.stream(
            "GET", f"/api/research/{session_id}/events"
        ) as response:
            timeline = "".join(response.iter_text())

    assert restored["status"] == "complete"
    assert restored["board"]["title"].startswith("Crossing the Bitterroots")
    assert '"event_type":"mcp_tool_call"' in timeline
    assert '"row_count":' in timeline
    assert '"access_path":"mcp_runtime"' in timeline
    assert '"sql":' in timeline

    clickhouse = get_clickhouse_client()
    rolled_up = clickhouse.query(
        """
SELECT countMerge(event_count), avgMerge(average_duration),
       quantilesMerge(0.5, 0.95)(duration_quantiles)
FROM sourcecut.research_stage_stats
WHERE event_type = 'mcp_tool_call'
"""
    ).result_rows[0]
    ttl = clickhouse.query(
        """
SELECT create_table_query
FROM system.tables
WHERE database = 'sourcecut' AND name = 'research_events'
"""
    ).result_rows[0][0]
    assert int(rolled_up[0]) >= 3
    assert float(rolled_up[1]) >= 0
    assert "toIntervalDay(90)" in str(ttl)
