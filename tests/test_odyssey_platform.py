from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sourcecut_api.evaluation import score_odyssey_answers, score_odyssey_invariants
from sourcecut_api.integrations.clickhouse_mcp import (
    ClickHouseMcpClient,
    ClickHouseMcpSettings,
    McpToolCallError,
    validate_mcp_query,
)
from sourcecut_api.main import create_app
from sourcecut_api.services.odyssey_board import MemoryBoardStore
from sourcecut_api.services.readiness import readiness_report

ROOT = Path(__file__).resolve().parents[1]


def settings(**overrides: object) -> ClickHouseMcpSettings:
    values: dict[str, object] = {
        "url": "https://mcp.example.test/mcp",
        "auth_token": "secret",
        "max_result_rows": 500,
        "max_result_bytes": 500,
    }
    values.update(overrides)
    return ClickHouseMcpSettings(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "query",
    [
        "DROP TABLE sourcecut.passages",
        "SELECT passage_id FROM sourcecut.passages LIMIT 501",
        "SELECT passage_id FROM sourcecut.passages LIMIT 1 SETTINGS max_execution_time=0",
        "SELECT passage_id FROM sourcecut.passages LIMIT 1; SELECT 1 LIMIT 1",
        "SELECT passage_id FROM sourcecut.passages -- hidden\nLIMIT 1",
    ],
)
def test_runtime_mcp_query_policy_rejects_unbounded_or_unsafe_sql(query: str) -> None:
    assert validate_mcp_query(query, settings()) is not None


def test_runtime_mcp_policy_accepts_bounded_read_query() -> None:
    assert (
        validate_mcp_query(
            "SELECT passage_id FROM sourcecut.odyssey_text_lookup_v LIMIT 100",
            settings(),
        )
        is None
    )


def test_runtime_mcp_enforces_response_byte_and_row_caps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ClickHouseMcpClient(settings(max_result_rows=2, max_result_bytes=100))

    class Session:
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
            del name, arguments
            return SimpleNamespace(
                isError=False,
                structuredContent={"columns": ["value"], "rows": [["x" * 150]]},
                content=[],
            )

    class Context:
        async def __aenter__(self) -> Session:
            return Session()

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(client, "_session", lambda: Context())
    with pytest.raises(McpToolCallError, match="byte limit"):
        asyncio.run(client.call_tool("run_query", {"query": "SELECT value LIMIT 1"}))


def test_request_safety_limits_payloads_rates_and_sets_headers() -> None:
    with TestClient(create_app(board_store=MemoryBoardStore())) as client:
        healthy = client.get("/healthz", headers={"X-Request-ID": "request-123"})
        assert healthy.headers["X-Request-ID"] == "request-123"
        assert healthy.headers["X-Content-Type-Options"] == "nosniff"
        oversized = client.post(
            "/api/v1/boards",
            content=b"x",
            headers={"Content-Length": "1000001", "Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
        responses = [client.get("/api/v1/search/text?q=x") for _ in range(31)]
        assert responses[-1].status_code == 429
        assert int(responses[-1].headers["Retry-After"]) >= 1


def test_ready_endpoint_proves_offline_cache_and_reports_degraded_live_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLICKHOUSE_MCP_URL", raising=False)
    monkeypatch.delenv("CLICKHOUSE_MCP_AUTH_TOKEN", raising=False)
    report = readiness_report()
    assert report["status"] == "degraded"
    assert report["offline_corpus_ready"] is True
    assert report["live_research_configured"] is False
    assert report["failures"] == []
    with TestClient(create_app(board_store=MemoryBoardStore())) as client:
        assert client.get("/readyz").json()["offline_corpus_ready"] is True


def test_security_ddl_has_role_limits_policies_and_allowlisted_grants() -> None:
    sql = (ROOT / "sql/security/odyssey_mcp_role.sql").read_text(encoding="utf-8")
    assert "readonly = 2" in sql
    assert "max_execution_time = 10" in sql
    assert "max_result_rows = 500" in sql
    assert "TO ALL EXCEPT sourcecut_mcp_role" in sql
    assert "trusted = 1 AND validation_status = 'valid'" in sql
    assert "GRANT SELECT ON sourcecut.odyssey_trusted_claim_evidence_v" in sql
    assert "GRANT INSERT" not in sql
    assert "GRANT ALL" not in sql


def test_odyssey_invariants_and_gold_scoring() -> None:
    invariant_report = score_odyssey_invariants(ROOT)
    assert invariant_report["passes"] is True, invariant_report["failures"]
    gold = json.loads(
        (ROOT / "fixtures/evaluation/odyssey_gold_questions.json").read_text(encoding="utf-8")
    )
    answers = {
        "answers": [
            {
                "question_id": question["question_id"],
                "status": question["expected_status"],
                "reference_ids": question["expected_reference_ids"],
            }
            for question in gold["questions"]
        ]
    }
    report = score_odyssey_answers(gold, answers)
    assert report["precision"] == 1
    assert report["recall"] == 1
    assert report["failures"] == []


def test_historical_dashboard_routes_remain_registered() -> None:
    paths = {
        route.path
        for route in create_app(board_store=MemoryBoardStore()).routes
        if hasattr(route, "path")
    }
    assert "/api/research" in paths
    assert "/api/research/{session_id}" in paths
    assert "/api/previs/jobs/{job_id}" in paths
