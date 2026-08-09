from __future__ import annotations

from types import SimpleNamespace

import pytest

from sourcecut_api.agents.research import (
    RESEARCH_INSTRUCTION,
    build_research_runtime,
    validate_analytical_query,
)
from sourcecut_api.integrations.clickhouse_mcp import ClickHouseMcpSettings


def local_settings(**overrides: object) -> ClickHouseMcpSettings:
    values: dict[str, object] = {
        "url": "http://127.0.0.1:8000/mcp",
        "auth_token": "test-token",
    }
    values.update(overrides)
    return ClickHouseMcpSettings(**values)  # type: ignore[arg-type]


def test_mcp_settings_require_authentication() -> None:
    with pytest.raises(ValueError, match="AUTH_TOKEN"):
        local_settings(auth_token="").validate()

    local_settings(auth_token="", allow_unauthenticated_local=True).validate()


def test_hosted_mcp_requires_https_even_with_a_token() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        local_settings(url="http://mcp.example.com/mcp").validate()

    local_settings(url="https://mcp.example.com/mcp").validate()


def test_research_agent_has_only_mcp_toolset_and_deterministic_lookup() -> None:
    runtime = build_research_runtime(local_settings(), model="gemini-test")

    assert runtime.agent.model == "gemini-test"
    assert len(runtime.agent.tools) == 2
    assert runtime.agent.tools[1].__name__ == "get_passage"
    assert "list_databases and list_tables" in runtime.agent.instruction
    assert "trusted=true" in runtime.agent.instruction
    assert "UNSUPPORTED" in runtime.agent.instruction


@pytest.mark.parametrize(
    ("query", "expected_error"),
    [
        ("DROP TABLE sourcecut.passages LIMIT 1", "only SELECT"),
        ("SELECT * FROM sourcecut.passages LIMIT 10", "explicit columns"),
        (
            "SELECT passage_id FROM sourcecut.passages LIMIT 10",
            "entry_date BETWEEN",
        ),
        (
            "SELECT passage_id FROM other.passages "
            "WHERE entry_date BETWEEN 18050909 AND 18050930 LIMIT 10",
            "outside SourceCut",
        ),
        (
            "SELECT passage_id FROM sourcecut.passages "
            "WHERE entry_date BETWEEN 18050909 AND 18050930 LIMIT 201",
            "no greater than 200",
        ),
        (
            "SELECT passage_id FROM sourcecut.passages "
            "WHERE entry_date BETWEEN 18050909 AND 18050930 "
            "LIMIT 10 SETTINGS max_execution_time=1",
            "settings-changing",
        ),
    ],
)
def test_agent_generated_query_guardrails(query: str, expected_error: str) -> None:
    assert expected_error in (validate_analytical_query(query) or "")


def test_approved_passage_query_passes_guardrails() -> None:
    query = """
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages
WHERE entry_date BETWEEN 18050909 AND 18050930
  AND positionCaseInsensitiveUTF8(passage_text, 'snow') > 0
LIMIT 20
"""
    assert validate_analytical_query(query) is None


def test_research_instruction_documents_schema_and_citations() -> None:
    for phrase in (
        "sourcecut.passages",
        "sourcecut.observations",
        "passage_id",
        "author_display_name",
        "exact quote",
        "always use exactly entry_date BETWEEN 18050909 AND 18050930",
        "modern words \"Bitterroot\"",
        "entry_date BETWEEN",
        "INNER JOIN",
    ):
        assert phrase in RESEARCH_INSTRUCTION


def test_query_callback_allows_non_query_mcp_tools() -> None:
    runtime = build_research_runtime(local_settings(), model="gemini-test")
    callback = runtime.agent.before_tool_callback
    assert (
        callback(
            tool=SimpleNamespace(name="list_tables"),
            args={"database": "sourcecut"},
            tool_context=None,
        )
        is None
    )


def test_query_callback_removes_one_trailing_statement_delimiter() -> None:
    runtime = build_research_runtime(local_settings(), model="gemini-test")
    callback = runtime.agent.before_tool_callback
    args = {
        "query": (
            "SELECT passage_id FROM sourcecut.passages "
            "WHERE entry_date BETWEEN 18050909 AND 18050930 LIMIT 10;"
        )
    }

    assert callback(tool=SimpleNamespace(name="run_query"), args=args, tool_context=None) is None
    assert not args["query"].endswith(";")
