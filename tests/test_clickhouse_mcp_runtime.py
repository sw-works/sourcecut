from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any

import pytest

from sourcecut_api.agents.research import (
    RESEARCH_INSTRUCTION,
    _observe_adk_tool,
    build_research_runtime,
    validate_analytical_query,
)
from sourcecut_api.integrations.clickhouse_mcp import (
    ClickHouseMcpClient,
    ClickHouseMcpSettings,
)
from sourcecut_api.models.linguistic import (
    CooccurrenceRequest,
    FormulaSearchRequest,
    FrequencyRequest,
    TextSearchRequest,
)


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


def test_deterministic_asset_lookup_uses_fixed_mcp_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ClickHouseMcpClient(local_settings())
    queries: list[str] = []

    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        assert name == "run_query"
        queries.append(arguments["query"])
        return {
            "columns": ["asset_id", "provider", "metadata_sha256"],
            "rows": [["loc:map", "Library of Congress", b"a" * 64]],
        }

    monkeypatch.setattr(client, "call_tool", call_tool)
    result = asyncio.run(client.get_asset("loc:map"))

    assert result["status"] == "found"
    assert result["asset"]["metadata_sha256"] == "a" * 64
    assert "FROM sourcecut.media_assets FINAL" in queries[0]
    assert "WHERE asset_id = 'loc:map'" in queries[0]


def test_odyssey_linguistic_lookups_use_governed_mcp_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ClickHouseMcpClient(local_settings())
    queries: list[str] = []

    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        assert name == "run_query"
        queries.append(arguments["query"])
        return {"columns": [], "rows": []}

    monkeypatch.setattr(client, "call_tool", call_tool)
    asyncio.run(client.search_odyssey_text(TextSearchRequest(query="πολύτροπος", mode="lemma")))
    asyncio.run(client.get_odyssey_frequency(FrequencyRequest(query="πολύτροπος")))
    asyncio.run(client.get_odyssey_formulae(FormulaSearchRequest(query="πολύτροπον")))
    asyncio.run(
        client.get_odyssey_cooccurrences(
            CooccurrenceRequest(left_lemma="ἀνήρ", right_lemma="πολύτροπος")
        )
    )

    assert "sourcecut.odyssey_lemma_occurrences_v" in queries[0]
    assert "lemma_search = 'πολυτροποσ'" in queries[0]
    assert "sourcecut.odyssey_lemma_occurrences_v" in queries[1]
    assert "sourcecut.odyssey_formula_occurrences_v" in queries[2]
    assert queries[3].count("sourcecut.odyssey_lemma_occurrences_v") == 2
    assert all("INSERT" not in query for query in queries)


def test_odyssey_search_escapes_literals_and_refuses_unavailable_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ClickHouseMcpClient(local_settings())
    queries: list[str] = []

    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        del name
        queries.append(arguments["query"])
        return {"columns": [], "rows": []}

    monkeypatch.setattr(client, "call_tool", call_tool)
    asyncio.run(client.search_odyssey_text(TextSearchRequest(query="man's", mode="english")))

    assert "man''s" in queries[0]
    with pytest.raises(ValueError, match="reviewed annotation"):
        asyncio.run(
            client.search_odyssey_text(
                TextSearchRequest(query="ἀνήρ", mode="lemma", speaker_ids=("odysseus",))
            )
        )


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
            "SELECT passage_id FROM sourcecut.passages FINAL "
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
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN 18050909 AND 18050930
  AND hasToken(lower(passage_text), 'snow')
LIMIT 20
"""
    assert validate_analytical_query(query) is None


def test_raw_replacing_table_query_requires_final() -> None:
    query = """
SELECT passage_id
FROM sourcecut.passages
WHERE entry_date BETWEEN 18050909 AND 18050930
LIMIT 20
"""

    assert "require FINAL" in (validate_analytical_query(query) or "")


def test_bare_table_name_also_requires_final() -> None:
    query = """
SELECT passage_id
FROM passages
WHERE entry_date BETWEEN 18050909 AND 18050930
LIMIT 20
"""

    assert "require FINAL" in (validate_analytical_query(query) or "")


def test_aliased_final_is_accepted() -> None:
    query = """
SELECT p.passage_id
FROM sourcecut.passages AS p FINAL
WHERE p.entry_date BETWEEN 18050909 AND 18050930
LIMIT 20
"""

    assert validate_analytical_query(query) is None


def test_media_assets_are_queryable_with_final() -> None:
    query = """
SELECT asset_id, title, rights_status
FROM sourcecut.media_assets FINAL
LIMIT 20
"""

    assert validate_analytical_query(query) is None


def test_semantic_query_with_float_array_passes_guardrails() -> None:
    query = """
SELECT passage_id, cosineDistance(embedding, [0.1, -0.2, 3e-4]) AS distance
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN 18050909 AND 18050930 AND notEmpty(embedding)
ORDER BY distance
LIMIT 40
"""

    assert validate_analytical_query(query) is None


def test_mutation_text_hidden_in_array_literal_is_rejected() -> None:
    query = """
SELECT passage_id, cosineDistance(embedding, [0.1, 'DROP TABLE passages']) AS distance
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN 18050909 AND 18050930
LIMIT 40
"""

    assert "mutating" in (validate_analytical_query(query) or "")


def test_only_curated_term_dictionary_is_allowed() -> None:
    approved = """
SELECT dictGet('sourcecut.term_expansion_dict', 'expansions', tuple('food', 'hunger'))
LIMIT 1
"""
    rejected = "SELECT dictGet('sourcecut.secret_dict', 'value', tuple('x')) LIMIT 1"

    assert validate_analytical_query(approved) is None
    assert "unapproved dictionary" in (validate_analytical_query(rejected) or "")


def test_approved_parameterized_view_query_passes_guardrails() -> None:
    query = """
SELECT *
FROM sourcecut.evidence_window(start=18050909, end=18050930, limit=20)
LIMIT 20
"""
    assert validate_analytical_query(query) is None


def test_unknown_parameterized_view_is_rejected() -> None:
    query = "SELECT * FROM sourcecut.unknown_view(start=1) LIMIT 20"

    assert "unknown parameterized view" in (validate_analytical_query(query) or "")


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
            "SELECT passage_id FROM sourcecut.passages FINAL "
            "WHERE entry_date BETWEEN 18050909 AND 18050930 LIMIT 10;"
        )
    }

    assert callback(tool=SimpleNamespace(name="run_query"), args=args, tool_context=None) is None
    assert not args["query"].endswith(";")


def test_adk_tool_callback_records_sanitized_mcp_event(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[dict[str, object]] = []

    class FakeRepository:
        def __init__(self, client: object) -> None:
            del client

        def record(self, **values: object) -> None:
            recorded.append(values)

    monkeypatch.setenv("CLICKHOUSE_HOST", "example.clickhouse.cloud")
    monkeypatch.setattr(
        "sourcecut_api.agents.research.ResearchEventRepository", FakeRepository
    )
    monkeypatch.setattr(
        "sourcecut_api.agents.research.get_clickhouse_client", lambda: object()
    )
    started = time.time_ns() - 5_000_000
    context = SimpleNamespace(
        state={"temp:sourcecut.tool.started_ns.run_query": started},
        session=SimpleNamespace(id="session-1"),
    )

    _observe_adk_tool(
        SimpleNamespace(name="run_query"),
        {"query": "SELECT passage_id FROM sourcecut.passages FINAL LIMIT 2"},
        context,
        {"structuredContent": {"result": json.dumps({"rows": [[1], [2]]})}},
    )

    assert recorded[0]["event_type"] == "mcp_tool_call"
    assert recorded[0]["session_id"] == "session-1"
    payload = recorded[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["row_count"] == 2
    assert payload["access_path"] == "mcp_runtime"
