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

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.adk.tools.base_tool import BaseTool
from google.genai import types
from opentelemetry.trace import SpanKind

from sourcecut_api.agents.activity import ActivitySink, ActivityStreamPlugin
from sourcecut_api.integrations.clickhouse_mcp import (
    SMUGGLED_STATEMENT_PATTERN,
    ClickHouseMcpClient,
    ClickHouseMcpSettings,
    build_mcp_toolset,
    strip_sql_literals,
)
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
    "sourcecut.author_date_matrix",
    "sourcecut.evidence_window",
    "sourcecut.entities",
    "sourcecut.entity_mentions",
    "sourcecut.entity_mentions_window",
    "sourcecut.passage_lookup",
    "sourcecut.journal_entries",
    "sourcecut.observations",
    "sourcecut.passages",
    "sourcecut.sources",
    "sourcecut.route_waypoints",
    "sourcecut.term_expansions",
    "sourcecut.media_assets",
    "journal_entries",
    "observations",
    "passages",
    "media_assets",
    "sources",
    "system.columns",
    "system.tables",
}
ALLOWED_PARAMETERIZED_VIEWS = {
    "sourcecut.author_term_presence",
    "sourcecut.author_date_matrix",
    "sourcecut.evidence_window",
    "sourcecut.entity_mentions_window",
    "sourcecut.passage_lookup",
}
# Bare and qualified spellings both count: ALLOWED_TABLES admits bare names, so
# the FINAL requirement must catch them too.
REPLACING_TABLES = {
    "sourcecut.journal_entries",
    "sourcecut.media_assets",
    "sourcecut.observations",
    "sourcecut.passages",
    "journal_entries",
    "media_assets",
    "observations",
    "passages",
}
MUTATING_SQL = re.compile(
    r"\b(ALTER|ATTACH|CREATE|DELETE|DETACH|DROP|GRANT|INSERT|KILL|OPTIMIZE|RENAME|REVOKE|SET|SETTINGS|SYSTEM|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)
TABLE_REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE)
PARAMETERIZED_VIEW_CALL = re.compile(
    r"\bFROM\s+(sourcecut\.[A-Za-z_][A-Za-z0-9_]*)\s*\(", re.IGNORECASE
)
# `LIMIT 200` and `evidence_window(..., limit=200)` both cap rows, and the
# instruction tells the agent to prefer the parametrized views, so reading only
# the clause form refused exactly the queries the agent is asked to write.
LIMIT_CLAUSE = re.compile(r"\bLIMIT\s*(?:=\s*)?(\d+)\b", re.IGNORECASE)
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

PLAN_STAGE_INSTRUCTION = """
You plan a research pass over the SourceCut primary-source corpus. You have no tools and no
access to the corpus, so you cannot know what it contains: do not state historical facts and do
not predict what will be found.

Read the filmmaker's request and write a short plan:
1. The entry_date window to search, as YYYYMMDD bounds. Use the window the request implies; for
   the Bitterroot crossing that is 18050909 to 18050930.
2. Two to six evidence categories worth investigating, drawn from weather, terrain,
   transportation, food, shelter, equipment, person, animal, place, health, and event.
3. For each category, the period search vocabulary a journal keeper in 1805 would have written,
   and what would count as sufficient evidence.

Keep it under 200 words. The next agent retrieves the evidence; your plan only tells it where
to look.
""".strip()

AUDIT_STAGE_INSTRUCTION = """
You audit a research brief that another agent produced from the SourceCut corpus. You have no
tools: you can only check the brief against the retrieved evidence already in the conversation.

For each claim in the brief:
- confirm it names a passage_id, an author, an entry_date, and an exact quote that appears in
  the retrieved rows;
- flag any claim whose citation is missing, whose quote does not appear in what ClickHouse
  returned, or that generalizes past its evidence;
- flag any claim that rests on one author but is presented as established.

Report what is properly cited, what must be downgraded to SINGLE_SOURCE, and what must be
withdrawn as UNSUPPORTED. Do not add new historical claims and do not repair a citation from
your own knowledge. If everything checks out, say so plainly.
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
    # Keyword checks read the statement's structure, never its search
    # vocabulary: the period token `set`, from the attested "set out", is not a
    # SETTINGS clause. See strip_sql_literals.
    structure = strip_sql_literals(normalized)
    if not normalized or ";" in structure:
        return "run_query accepts exactly one SQL statement"
    if not re.match(r"^(SELECT|WITH|EXPLAIN)\b", normalized, re.IGNORECASE):
        return "run_query accepts only SELECT, WITH, or EXPLAIN"
    if MUTATING_SQL.search(structure) or SMUGGLED_STATEMENT_PATTERN.search(normalized):
        return "run_query rejected a mutating or settings-changing statement"
    dictionaries = {name.lower() for name in DICTIONARY_CALL.findall(normalized)}
    if dictionaries - {"sourcecut.term_expansion_dict"}:
        return "run_query referenced an unapproved dictionary"
    view_calls = {match.lower() for match in PARAMETERIZED_VIEW_CALL.findall(normalized)}
    unknown_views = view_calls - ALLOWED_PARAMETERIZED_VIEWS
    if unknown_views:
        names = ", ".join(sorted(unknown_views))
        return f"run_query referenced an unknown parameterized view: {names}"
    limits = [int(value) for value in LIMIT_CLAUSE.findall(structure)]
    if not limits or max(limits) > 200:
        return "run_query requires a literal LIMIT no greater than 200"
    referenced_tables = {match.lower() for match in TABLE_REFERENCE.findall(structure)}
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
        # Accept an optional alias between the table and FINAL:
        # "FROM sourcecut.passages FINAL", "... AS p FINAL", "... p FINAL".
        if not re.search(
            rf"\b(?:FROM|JOIN)\s+{re.escape(table)}"
            rf"(?:\s+(?:AS\s+)?(?!FINAL\b)[A-Za-z_][A-Za-z0-9_]*)?\s+FINAL\b",
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
    # The user-facing timeline is ActivityStreamPlugin's job; this callback keeps
    # only the span and the metrics, so a tool call is recorded once in each place.
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


def build_research_pipeline(
    settings: ClickHouseMcpSettings | None = None,
    *,
    model: str | None = None,
) -> ResearchRuntime:
    """Three specialists in sequence instead of one generalist.

    The planner has no tools at all, so it cannot reach the corpus and cannot
    smuggle a claim in as a plan. The researcher holds the ClickHouse tools
    under the same query guardrail as the single agent. The auditor also runs
    without tools and sees only what the researcher returned, so its job is to
    find claims that outran their citations rather than to fetch more.

    Each stage writes to a named output key, so the handoff between them is
    inspectable state rather than a shared scratchpad.
    """
    resolved = settings or ClickHouseMcpSettings.from_env()
    client = ClickHouseMcpClient(resolved)
    toolset = build_mcp_toolset(resolved)
    resolved_model = model or os.getenv("GEMINI_MODEL", DEFAULT_RESEARCH_MODEL)

    planner = LlmAgent(
        name="sourcecut_planner",
        description="Decides which corpus window and evidence categories to investigate",
        model=resolved_model,
        instruction=PLAN_STAGE_INSTRUCTION,
        output_key="research_plan",
    )
    researcher = LlmAgent(
        name="sourcecut_evidence",
        description="Retrieves cited evidence through the read-only ClickHouse MCP server",
        model=resolved_model,
        instruction=RESEARCH_INSTRUCTION,
        tools=[toolset, _build_get_passage_tool(client)],
        before_tool_callback=_guard_mcp_query,
        after_tool_callback=_observe_adk_tool,
        output_key="research_findings",
    )
    auditor = LlmAgent(
        name="sourcecut_auditor",
        description="Checks that every claim carries a citation returned by ClickHouse",
        model=resolved_model,
        instruction=AUDIT_STAGE_INSTRUCTION,
        output_key="research_audit",
    )
    pipeline = SequentialAgent(
        name="sourcecut_research_pipeline",
        description=(
            "Plan, retrieve, and audit evidence-grounded production research"
        ),
        sub_agents=[planner, researcher, auditor],
    )
    return ResearchRuntime(agent=pipeline, mcp_client=client, mcp_toolset=toolset)


async def run_research_session(
    question: str,
    session_id: str,
    *,
    pipeline: bool = False,
    sink: ActivitySink | None = None,
    user_id: str = "sourcecut",
) -> str:
    """Run one ADK research question, reporting activity as it happens.

    `sink` receives an event per agent, model call and tool call while the run is
    in flight — the same six-argument signature `ResearchBoardService.event_sink`
    uses, so the caller can hand over whatever already writes its timeline. The
    return value is the agent's final text; the interesting part arrived earlier,
    through the sink.
    """
    runtime = build_research_pipeline() if pipeline else build_research_runtime()
    plugins = [ActivityStreamPlugin(sink=sink)] if sink is not None else []
    runner = InMemoryRunner(
        app=App(name="sourcecut", root_agent=runtime.agent, plugins=plugins)
    )
    answer: list[str] = []
    try:
        with telemetry_span(
            "sourcecut.research.session",
            {
                "sourcecut.research.session_id": session_id,
                "sourcecut.research.runtime": "google_adk",
            },
        ):
            add_counter(
                "sourcecut.research.sessions",
                1,
                {"runtime": "pipeline" if pipeline else "single_agent"},
            )
            await runner.session_service.create_session(
                app_name="sourcecut", user_id=user_id, session_id=session_id
            )
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=question)]),
            ):
                # Sub-agents each produce a final response; the last one standing
                # is the auditor's, which is what a reader should be handed.
                if event.is_final_response() and event.content:
                    text = "".join(part.text or "" for part in event.content.parts or ())
                    if text.strip():
                        answer.append(text.strip())
    finally:
        await runner.close()
        await runtime.close()
    return answer[-1] if answer else ""


async def _run_question(question: str, session_id: str, *, pipeline: bool = False) -> None:
    configure_telemetry()

    def report(
        event_type: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any],
        duration_ms: int,
    ) -> None:
        del payload
        elapsed = f" ({duration_ms}ms)" if duration_ms else ""
        print(f"[{stage}/{status}] {event_type}: {message}{elapsed}", flush=True)

    try:
        answer = await run_research_session(
            question, session_id, pipeline=pipeline, sink=report
        )
    finally:
        force_flush_telemetry()
    print(answer)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one SourceCut ADK research question")
    parser.add_argument("question")
    parser.add_argument("--session-id", default=f"research-{uuid.uuid4()}")
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="Run the planner/researcher/auditor sequence instead of one agent",
    )
    args = parser.parse_args()
    # ADK reads the same environment google-genai does, so this only checks that
    # one of the two backends is actually configured before the run starts.
    from sourcecut_api.integrations.genai import GenaiSettings

    if not GenaiSettings.from_env().configured:
        raise SystemExit(
            "Set GOOGLE_GENAI_USE_VERTEXAI=true with GOOGLE_CLOUD_PROJECT, "
            "or GEMINI_API_KEY, before running research"
        )
    asyncio.run(_run_question(args.question, args.session_id, pipeline=args.pipeline))
