from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult
from opentelemetry.trace import SpanKind

from sourcecut_api.telemetry import (
    add_counter,
    observe_histogram,
    sanitize_sql,
    telemetry_span,
)

MCP_TOOL_NAMES = ("list_databases", "list_tables", "run_query")
PASSAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,256}$")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of true/false, 1/0, yes/no, or on/off")


@dataclass(frozen=True, slots=True)
class ClickHouseMcpSettings:
    url: str = "http://127.0.0.1:8000/mcp"
    auth_token: str = ""
    timeout_seconds: float = 60.0
    allow_unauthenticated_local: bool = False

    @classmethod
    def from_env(cls) -> ClickHouseMcpSettings:
        settings = cls(
            url=os.getenv("CLICKHOUSE_MCP_URL", "http://127.0.0.1:8000/mcp"),
            auth_token=os.getenv("CLICKHOUSE_MCP_AUTH_TOKEN", ""),
            timeout_seconds=float(os.getenv("CLICKHOUSE_MCP_CLIENT_TIMEOUT", "60")),
            allow_unauthenticated_local=_env_bool(
                "SOURCECUT_ALLOW_UNAUTHENTICATED_MCP", False
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("CLICKHOUSE_MCP_URL must be an HTTP(S) URL")
        is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if not is_loopback and parsed.scheme != "https":
            raise ValueError("Hosted CLICKHOUSE_MCP_URL must use HTTPS")
        if not self.auth_token and not (
            is_loopback and self.allow_unauthenticated_local
        ):
            raise ValueError(
                "CLICKHOUSE_MCP_AUTH_TOKEN is required; unauthenticated MCP is local-only"
            )
        if self.timeout_seconds <= 0:
            raise ValueError("CLICKHOUSE_MCP_CLIENT_TIMEOUT must be positive")

    @property
    def headers(self) -> dict[str, str] | None:
        if not self.auth_token:
            return None
        return {"Authorization": f"Bearer {self.auth_token}"}


class McpToolCallError(RuntimeError):
    pass


class ClickHouseMcpClient:
    def __init__(self, settings: ClickHouseMcpSettings) -> None:
        settings.validate()
        self._settings = settings

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        async with streamablehttp_client(
            self._settings.url,
            headers=self._settings.headers,
            timeout=self._settings.timeout_seconds,
            sse_read_timeout=self._settings.timeout_seconds,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def list_tools(self) -> tuple[str, ...]:
        async with self._session() as session:
            tools = await session.list_tools()
        return tuple(tool.name for tool in tools.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in MCP_TOOL_NAMES:
            raise ValueError(f"Unsupported ClickHouse MCP tool: {name}")
        attributes: dict[str, str | bool | int | float] = {
            "sourcecut.access.path": "mcp_runtime",
            "sourcecut.mcp.tool.name": name,
            "db.system.name": "clickhouse",
            "server.address": urlparse(self._settings.url).hostname or "unknown",
        }
        query = arguments.get("query")
        if isinstance(query, str):
            attributes["db.query.text"] = sanitize_sql(query)
            attributes["db.operation.name"] = "SELECT"
        started = time.perf_counter()
        try:
            with telemetry_span(
                f"clickhouse.mcp.{name}", attributes, kind=SpanKind.CLIENT
            ) as span:
                async with self._session() as session:
                    result = await session.call_tool(name, arguments=arguments)
                payload = _decode_tool_result(result)
                returned_rows = _returned_rows(payload)
                span.set_attribute("db.response.returned_rows", returned_rows)
                add_counter(
                    "sourcecut.mcp.calls",
                    1,
                    {"tool": name, "status": "success"},
                )
                add_counter("sourcecut.mcp.rows", returned_rows, {"tool": name})
                return payload
        except Exception:
            add_counter("sourcecut.mcp.calls", 1, {"tool": name, "status": "failure"})
            raise
        finally:
            observe_histogram(
                "sourcecut.mcp.duration",
                (time.perf_counter() - started) * 1000,
                {"tool": name},
            )

    async def get_passage(self, passage_id: str) -> dict[str, Any]:
        if not PASSAGE_ID_PATTERN.fullmatch(passage_id):
            raise ValueError("passage_id contains unsupported characters")
        query = f"""
SELECT
    passage_id,
    entry_id,
    source_id,
    author_id,
    author_display_name,
    entry_date,
    passage_index,
    char_start,
    char_end,
    passage_text,
    passage_sha256
FROM sourcecut.passages
WHERE passage_id = '{passage_id}'
LIMIT 2
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        if not rows:
            return {"status": "not_found", "passage_id": passage_id}
        if len(rows) > 1:
            raise RuntimeError(f"Duplicate passage_id in ClickHouse: {passage_id}")
        row = rows[0]
        passage = row if isinstance(row, dict) else dict(zip(columns, row, strict=True))
        return {"status": "found", "passage": passage}


def build_mcp_toolset(settings: ClickHouseMcpSettings) -> McpToolset:
    settings.validate()
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=settings.url,
            headers=settings.headers,
            timeout=settings.timeout_seconds,
            sse_read_timeout=settings.timeout_seconds,
        ),
        tool_filter=list(MCP_TOOL_NAMES),
    )


@dataclass(frozen=True, slots=True)
class McpPreflightResult:
    adk_tools: tuple[str, ...]
    server_tools: tuple[str, ...]
    sourcecut_tables_reached: bool
    passage_count: int
    visual_evidence_authors: int
    wagon_mentions: int
    deterministic_snow_lookup: bool
    read_only_enforced: bool
    unauthenticated_status: int


async def run_mcp_preflight(
    settings: ClickHouseMcpSettings | None = None,
) -> McpPreflightResult:
    resolved = settings or ClickHouseMcpSettings.from_env()
    client = ClickHouseMcpClient(resolved)
    toolset = build_mcp_toolset(resolved)
    try:
        adk_tools = tuple(tool.name for tool in await toolset.get_tools())
    finally:
        await toolset.close()

    server_tools = await client.list_tools()
    tables = await client.call_tool("list_tables", {"database": "sourcecut"})
    sourcecut_tables_reached = "passages" in json.dumps(tables)
    count_payload = await client.call_tool(
        "run_query",
        {
            "query": (
                "SELECT count() AS passages FROM sourcecut.passages "
                "WHERE entry_date BETWEEN 18050909 AND 18050930 LIMIT 1"
            )
        },
    )
    columns, rows = _query_rows(count_payload)
    count_row = rows[0]
    passage_count = int(
        count_row["passages"]
        if isinstance(count_row, dict)
        else count_row[columns.index("passages")]
    )

    evidence_payload = await client.call_tool(
        "run_query",
        {
            "query": """
SELECT
    author_display_name,
    countIf(hasToken(lower(passage_text), 'snow')) AS snow,
    countIf(hasToken(lower(passage_text), 'horse')) AS horse,
    countIf(hasToken(lower(passage_text), 'mountain')) AS mountain,
    countIf(hasToken(lower(passage_text), 'wagon')) AS wagon
FROM sourcecut.passages
WHERE entry_date BETWEEN 18050909 AND 18050930
GROUP BY author_display_name
ORDER BY author_display_name
LIMIT 10
""".strip()
        },
    )
    evidence_columns, evidence_rows = _query_rows(evidence_payload)
    visual_evidence_authors = sum(
        1
        for row in evidence_rows
        if sum(int(row[evidence_columns.index(term)]) for term in ("snow", "horse", "mountain"))
        > 0
    )
    wagon_mentions = sum(
        int(row[evidence_columns.index("wagon")]) for row in evidence_rows
    )

    snow_payload = await client.call_tool(
        "run_query",
        {
            "query": """
SELECT passage_id
FROM sourcecut.passages
WHERE entry_date BETWEEN 18050909 AND 18050930
  AND hasToken(lower(passage_text), 'snow')
ORDER BY entry_date, author_id
LIMIT 1
""".strip()
        },
    )
    _, snow_rows = _query_rows(snow_payload)
    snow_passage_id = str(snow_rows[0][0])
    passage_lookup = await client.get_passage(snow_passage_id)
    deterministic_snow_lookup = (
        passage_lookup.get("status") == "found"
        and passage_lookup["passage"].get("passage_id") == snow_passage_id
        and "snow" in str(passage_lookup["passage"].get("passage_text", "")).lower()
    )

    read_only_enforced = False
    try:
        await client.call_tool(
            "run_query",
            {
                "query": (
                    "SELECT count() FROM sourcecut.passages LIMIT 1 "
                    "SETTINGS max_rows_to_read = 1000000"
                )
            },
        )
    except McpToolCallError as exc:
        read_only_enforced = "readonly" in str(exc).lower()
    if not read_only_enforced:
        raise RuntimeError("The MCP ClickHouse user did not enforce read-only settings")

    unauthenticated_status = _unauthenticated_mcp_status(resolved.url)
    if unauthenticated_status not in {401, 403}:
        raise RuntimeError(
            f"Unauthenticated MCP request returned HTTP {unauthenticated_status}"
        )
    if set(MCP_TOOL_NAMES) - set(adk_tools):
        raise RuntimeError("ADK did not discover every required ClickHouse MCP tool")
    if set(MCP_TOOL_NAMES) - set(server_tools):
        raise RuntimeError("Official MCP server did not expose every required tool")
    if not sourcecut_tables_reached:
        raise RuntimeError("MCP list_tables did not reach the SourceCut passages table")

    return McpPreflightResult(
        adk_tools=adk_tools,
        server_tools=server_tools,
        sourcecut_tables_reached=sourcecut_tables_reached,
        passage_count=passage_count,
        visual_evidence_authors=visual_evidence_authors,
        wagon_mentions=wagon_mentions,
        deterministic_snow_lookup=deterministic_snow_lookup,
        read_only_enforced=read_only_enforced,
        unauthenticated_status=unauthenticated_status,
    )


def _decode_tool_result(result: CallToolResult) -> Any:
    if result.isError:
        message = "\n".join(
            block.text for block in result.content if getattr(block, "type", None) == "text"
        )
        raise McpToolCallError(message or "ClickHouse MCP tool call failed")
    if result.structuredContent is not None:
        payload = result.structuredContent
        if set(payload) == {"result"} and isinstance(payload["result"], str):
            try:
                return json.loads(payload["result"])
            except json.JSONDecodeError:
                return payload["result"]
        return payload
    text_blocks = [
        block.text for block in result.content if getattr(block, "type", None) == "text"
    ]
    if not text_blocks:
        return None
    text = "\n".join(text_blocks)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _query_rows(payload: Any) -> tuple[list[str], list[Any]]:
    if not isinstance(payload, dict):
        raise RuntimeError("ClickHouse MCP run_query returned an unexpected payload")
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise RuntimeError("ClickHouse MCP run_query omitted columns or rows")
    return [str(column) for column in columns], rows


def _returned_rows(payload: Any) -> int:
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return len(payload["rows"])
    return 0


def _unauthenticated_mcp_status(url: str) -> int:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "sourcecut-preflight", "version": "0.1.0"},
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            add_counter(
                "sourcecut.mcp.authentication_failures",
                1,
                {"http.response.status_code": exc.code},
            )
        return exc.code


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the authenticated ClickHouse MCP path")
    parser.parse_args()
    result = asyncio.run(run_mcp_preflight())
    print(
        json.dumps(
            {
                "adk_tools": result.adk_tools,
                "server_tools": result.server_tools,
                "sourcecut_tables_reached": result.sourcecut_tables_reached,
                "passage_count": result.passage_count,
                "visual_evidence_authors": result.visual_evidence_authors,
                "wagon_mentions": result.wagon_mentions,
                "deterministic_snow_lookup": result.deterministic_snow_lookup,
                "read_only_enforced": result.read_only_enforced,
                "unauthenticated_status": result.unauthenticated_status,
            },
            indent=2,
        )
    )
