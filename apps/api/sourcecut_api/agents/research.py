from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools.base_tool import BaseTool
from opentelemetry.trace import SpanKind

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.integrations.clickhouse_mcp import (
    ClickHouseMcpClient,
    ClickHouseMcpSettings,
    build_mcp_toolset,
)
from sourcecut_api.repositories import ResearchEventRepository
from sourcecut_api.telemetry import (
    add_counter,
    configure_telemetry,
    force_flush_telemetry,
    observe_histogram,
    record_completed_span,
    sanitize_sql,
    telemetry_span,
)

DEFAULT_RESEARCH_MODEL = "gemini-2.5-flash"
ALLOWED_TABLES = {
    "sourcecut.author_term_presence",
    "sourcecut.evidence_window",
    "sourcecut.entities",
    "sourcecut.entity_mentions",
    "sourcecut.entity_mentions_window",
    "sourcecut.passage_lookup",
    "sourcecut.journal_entries",
    "sourcecut.observations",
    "sourcecut.passages",
    "sourcecut.sources",
    "sourcecut.term_expansions",
    "journal_entries",
    "observations",
    "passages",
    "sources",
    "system.columns",
    "system.tables",
}
ALLOWED_PARAMETERIZED_VIEWS = {
    "sourcecut.author_term_presence",
    "sourcecut.evidence_window",
    "sourcecut.entity_mentions_window",
    "sourcecut.passage_lookup",
}
REPLACING_TABLES = {
    "sourcecut.journal_entries",
    "sourcecut.media_assets",
    "sourcecut.observations",
    "sourcecut.passages",
}
MUTATING_SQL = re.compile(
    r"\b(ALTER|ATTACH|CREATE|DELETE|DETACH|DROP|GRANT|INSERT|KILL|OPTIMIZE|RENAME|REVOKE|SET|SETTINGS|SYSTEM|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)
TABLE_REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE)
PARAMETERIZED_VIEW_CALL = re.compile(
    r"\bFROM\s+(sourcecut\.[A-Za-z_][A-Za-z0-9_]*)\s*\(", re.IGNORECASE
)
LIMIT_CLAUSE = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)
DICTIONARY_CALL = re.compile(r"\bdictGet\s*\(\s*'([^']+)'", re.IGNORECASE)

RESEARCH_INSTRUCTION = """
You are SourceCut's historical research orchestrator. Historical claims must come from the
SourceCut ClickHouse corpus, never model memory.

Required workflow:
1. Use list_databases and list_tables before the first analytical query in a session.
2. Use run_query for every analytical retrieval. Never invent tool results or citations.
3. Cite each claim with passage_id, author_display_name, entry_date, and an exact quote returned by
   ClickHouse. Group corroborating evidence by author. Two authors are HIGH support; one author is
   SINGLE_SOURCE. If no returned passage supports a claim, label it UNSUPPORTED and say the corpus
   does not support it.
4. Use get_passage only to drill into a known passage_id. It performs a deterministic fixed query;
   never use it for search.
5. Return a compact production brief: at most five evidence categories and at most two strongest
   excerpts per author in each category. Do not dump every matching passage.

SourceCut schema:
- sourcecut.passages: passage_id, entry_id, source_id, author_id, author_display_name,
  entry_date Int32 (YYYYMMDD), passage_index, char_start, char_end, passage_text, passage_sha256,
  embedding, embedding_model.
  Sort key begins (entry_date, author_id).
- sourcecut.observations: observation_id, passage_id, category, canonical_term,
  normalized_description, explicit, source_quote, source_start, source_end, confidence, trusted,
  validation_status. Use only trusted=true AND validation_status='valid'.
- sourcecut.journal_entries: entry_id, source_id, author fields, entry_date Int32, raw_text.
- sourcecut.sources: source_id, provider, title, source_url, rights_status.
- sourcecut.evidence_window(start, end, limit): validated observation evidence joined to passages.
- sourcecut.author_term_presence(start, end, term): whole-token counts and passage ids per author.
- sourcecut.passage_lookup(pid): deterministic exact passage lookup used by the application.
- sourcecut.term_expansion_dict: curated retrieval vocabulary keyed by (category, term). Use
  dictGet('sourcecut.term_expansion_dict', 'expansions', (category, term)); expansions guide
  search and are never evidence.
- sourcecut.entities is curated reference data. Query trusted, quote-anchored mentions through
  sourcecut.entity_mentions_window(entity, start, end), then drill into returned passage ids.
- journal_entries, passages, observations, and media_assets use ReplacingMergeTree. The approved
  views already resolve versions; raw queries against those base tables must add FINAL.

Approved query patterns:
- Prefer evidence_window and author_term_presence for standard date-window and comparison questions.
  A row policy makes unvalidated observations invisible to the MCP role even for raw SQL.
- Semantic retrieval may order non-empty embedding arrays by cosineDistance. Similarity only
  surfaces candidates; cite exact stored passages and never present distance as evidence.
- Canonical Bitterroot prompt: always use exactly entry_date BETWEEN 18050909 AND 18050930; never
  widen it to the full month. Do not require the modern words "Bitterroot" or "crossing" to occur
  in the journals. Search that exact window for production vocabulary such as snow, rain, cold,
  mountain, steep, rock, trail, timber, horse, food, hunger, camp, clothing, and equipment, and
  compare returned authors.
- Date/term passage search: filter passages by entry_date BETWEEN YYYYMMDD AND YYYYMMDD, then use
  hasToken(lower(passage_text), lower('term')); select explicit columns; LIMIT <= 200. This is
  whole-token matching; query singular and plural forms separately when both are needed.
- Valid observation search: prefilter passages by entry_date, prefilter observations by trusted,
  validation_status, category/canonical_term, then INNER JOIN on passage_id; LIMIT <= 200.
- Cross-author comparison: use the same filtered join, GROUP BY canonical_term, aggregate authors
  with groupUniqArray(author_display_name), and retain passage IDs and exact source_quote values.
- Schema discovery: list_tables first; query system.columns only when column types are needed.

Every run_query must be one read-only SELECT/WITH/EXPLAIN statement, name only documented tables,
avoid SELECT *, include a literal LIMIT <= 200, and include entry_date bounds whenever passages or
journal_entries are read. Do not add SETTINGS: the read-only ClickHouse role enforces query limits.
""".strip()


@dataclass(slots=True)
class ResearchRuntime:
    agent: Agent
    mcp_client: ClickHouseMcpClient
    mcp_toolset: Any

    async def close(self) -> None:
        await self.mcp_toolset.close()


def validate_analytical_query(query: str) -> str | None:
    normalized = query.strip().rstrip(";").strip()
    if not normalized or ";" in normalized:
        return "run_query accepts exactly one SQL statement"
    if not re.match(r"^(SELECT|WITH|EXPLAIN)\b", normalized, re.IGNORECASE):
        return "run_query accepts only SELECT, WITH, or EXPLAIN"
    if MUTATING_SQL.search(normalized):
        return "run_query rejected a mutating or settings-changing statement"
    dictionaries = {name.lower() for name in DICTIONARY_CALL.findall(normalized)}
    if dictionaries - {"sourcecut.term_expansion_dict"}:
        return "run_query referenced an unapproved dictionary"
    view_calls = {match.lower() for match in PARAMETERIZED_VIEW_CALL.findall(normalized)}
    unknown_views = view_calls - ALLOWED_PARAMETERIZED_VIEWS
    if unknown_views:
        names = ", ".join(sorted(unknown_views))
        return f"run_query referenced an unknown parameterized view: {names}"
    limits = [int(value) for value in LIMIT_CLAUSE.findall(normalized)]
    if not limits or max(limits) > 200:
        return "run_query requires a literal LIMIT no greater than 200"
    referenced_tables = {match.lower() for match in TABLE_REFERENCE.findall(normalized)}
    unsupported = referenced_tables - ALLOWED_TABLES
    if unsupported:
        return f"run_query referenced tables outside SourceCut: {', '.join(sorted(unsupported))}"
    if re.search(r"\bSELECT\s+\*", normalized, re.IGNORECASE) and not (
        referenced_tables and referenced_tables <= ALLOWED_PARAMETERIZED_VIEWS
    ):
        return "run_query requires explicit columns for raw table reads"
    if referenced_tables & {
        "sourcecut.passages",
        "passages",
        "sourcecut.journal_entries",
        "journal_entries",
    } and not re.search(
        r"\bentry_date\s+BETWEEN\s+\d{8}\s+AND\s+\d{8}\b",
        normalized,
        re.IGNORECASE,
    ):
        return (
            "passage and journal searches require an entry_date BETWEEN YYYYMMDD AND YYYYMMDD bound"
        )
    missing_final = {
        table
        for table in referenced_tables & REPLACING_TABLES
        if not re.search(
            rf"\b(?:FROM|JOIN)\s+{re.escape(table)}\s+FINAL\b",
            normalized,
            re.IGNORECASE,
        )
    }
    if missing_final:
        return f"raw ReplacingMergeTree reads require FINAL: {', '.join(sorted(missing_final))}"
    return None


def _guard_mcp_query(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: Any,
) -> dict[str, str] | None:
    if tool.name == "run_query":
        query = str(args.get("query", ""))
        error = validate_analytical_query(query)
        if error:
            return {"error": error}
        args["query"] = query.strip().rstrip(";").strip()
    if tool_context is not None:
        tool_context.state[f"temp:sourcecut.tool.started_ns.{tool.name}"] = time.time_ns()
    return None


def _observe_adk_tool(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: Any,
    tool_response: dict[str, Any],
) -> None:
    ended_ns = time.time_ns()
    key = f"temp:sourcecut.tool.started_ns.{tool.name}"
    started_ns = int(tool_context.state.get(key, ended_ns))
    duration_ms = (ended_ns - started_ns) / 1_000_000
    status, returned_rows = _tool_response_details(tool_response)
    attributes: dict[str, str | bool | int | float] = {
        "sourcecut.adk.tool.name": tool.name,
        "sourcecut.tool.status": status,
        "sourcecut.research.session_id": tool_context.session.id,
        "sourcecut.access.path": (
            "mcp_runtime"
            if tool.name in {"list_databases", "list_tables", "run_query"}
            else "deterministic"
        ),
        "db.response.returned_rows": returned_rows,
    }
    query = args.get("query")
    if isinstance(query, str):
        attributes["db.system.name"] = "clickhouse"
        attributes["db.query.text"] = sanitize_sql(query)
    error_type = "tool_error" if status == "failure" else None
    record_completed_span(
        f"adk.tool.{tool.name}",
        started_ns,
        ended_ns,
        attributes,
        error_type=error_type,
        kind=SpanKind.CLIENT,
    )
    if os.getenv("CLICKHOUSE_HOST"):
        payload: dict[str, Any] = {
            "tool": tool.name,
            "access_path": attributes["sourcecut.access.path"],
            "row_count": returned_rows,
        }
        if isinstance(query, str):
            payload["sql"] = sanitize_sql(query)
        ResearchEventRepository(get_clickhouse_client()).record(
            session_id=tool_context.session.id,
            event_type="mcp_tool_call",
            stage="agent",
            status=status,
            message=f"ADK completed {tool.name}.",
            payload=payload,
            duration_ms=int(duration_ms),
        )
    add_counter("sourcecut.adk.tool.calls", 1, {"tool": tool.name, "status": status})
    observe_histogram("sourcecut.adk.tool.duration", duration_ms, {"tool": tool.name})


def _tool_response_details(response: dict[str, Any]) -> tuple[str, int]:
    serialized = json.dumps(response, default=str)
    failed = '"error"' in serialized.lower() or "failed:" in serialized.lower()
    status = "failure" if failed else "success"
    structured = response.get("structuredContent", {})
    raw_result = structured.get("result") if isinstance(structured, dict) else None
    if isinstance(raw_result, str):
        try:
            payload = json.loads(raw_result)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return status, len(payload["rows"])
    return status, 0


def _build_get_passage_tool(client: ClickHouseMcpClient) -> Any:
    async def get_passage(passage_id: str) -> dict[str, Any]:
        """Return one exact stored primary-source passage for a known SourceCut passage ID."""
        return await client.get_passage(passage_id)

    return get_passage


def build_research_runtime(
    settings: ClickHouseMcpSettings | None = None,
    *,
    model: str | None = None,
) -> ResearchRuntime:
    resolved = settings or ClickHouseMcpSettings.from_env()
    client = ClickHouseMcpClient(resolved)
    toolset = build_mcp_toolset(resolved)
    agent = Agent(
        name="sourcecut_research",
        description=(
            "Evidence-grounded production research over the SourceCut primary-source corpus"
        ),
        model=model or os.getenv("GEMINI_MODEL", DEFAULT_RESEARCH_MODEL),
        instruction=RESEARCH_INSTRUCTION,
        tools=[toolset, _build_get_passage_tool(client)],
        before_tool_callback=_guard_mcp_query,
        after_tool_callback=_observe_adk_tool,
    )
    return ResearchRuntime(agent=agent, mcp_client=client, mcp_toolset=toolset)


async def _run_question(question: str, session_id: str) -> None:
    configure_telemetry()
    runtime = build_research_runtime()
    runner = InMemoryRunner(agent=runtime.agent, app_name="sourcecut")
    try:
        with telemetry_span(
            "sourcecut.research.session",
            {
                "sourcecut.research.session_id": session_id,
                "sourcecut.research.runtime": "google_adk",
            },
        ):
            add_counter("sourcecut.research.sessions", 1)
            await runner.run_debug(
                question,
                session_id=session_id,
                quiet=False,
                verbose=True,
            )
    finally:
        await runner.close()
        await runtime.close()
        force_flush_telemetry()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one SourceCut ADK research question")
    parser.add_argument("question")
    parser.add_argument("--session-id", default=f"research-{uuid.uuid4()}")
    args = parser.parse_args()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key.startswith("replace-"):
        raise SystemExit("Set GEMINI_API_KEY or GOOGLE_API_KEY before running research")
    asyncio.run(_run_question(args.question, args.session_id))
