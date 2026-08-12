from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlparse

from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult
from opentelemetry.trace import SpanKind

from sourcecut_api.models.linguistic import (
    CooccurrenceRequest,
    FormulaSearchRequest,
    FrequencyRequest,
    SearchMode,
    TextSearchRequest,
)
from sourcecut_api.telemetry import (
    add_counter,
    observe_histogram,
    sanitize_sql,
    telemetry_span,
)

MCP_TOOL_NAMES = ("list_databases", "list_tables", "run_query")
PASSAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,256}$")
ASSET_ID_PATTERN = re.compile(r"^[A-Za-z0-9:_.-]{1,256}$")
VERSION_ID_PATTERN = re.compile(r"^odyssey-perseus-(?:grc2|eng3|eng4)$")
TOKEN_ID_PATTERN = re.compile(r"^token:[a-f0-9]{28}$")
CLAIM_SOURCE_ID_PATTERN = re.compile(r"^(?:text-unit|token|scholarship):[A-Za-z0-9:_.-]{1,280}$")
NARRATIVE_ID_PATTERN = re.compile(r"^(?:event:)?[A-Za-z0-9_-]{1,160}$")
READ_QUERY_PATTERN = re.compile(r"^(?:SELECT|WITH|EXPLAIN)\b", re.IGNORECASE)
UNSAFE_QUERY_PATTERN = re.compile(
    r"\b(?:ALTER|ATTACH|CREATE|DELETE|DETACH|DROP|GRANT|INSERT|KILL|OPTIMIZE|"
    r"RENAME|REVOKE|SET|SETTINGS|SYSTEM|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)
QUERY_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)


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


def _accentless(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value).casefold()
        if not unicodedata.combining(character) and character not in "ʼ’'᾽"
    )


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _array_overlap(field: str, values: list[str]) -> str:
    return f"hasAny({field}, [{','.join(map(_sql_string, values))}])"


def _odyssey_annotation_filters(
    request: TextSearchRequest,
    version: str,
    book: str,
    line_start: str,
    line_end: str,
) -> str:
    filters = []
    if request.speaker_ids:
        filters.append(
            "EXISTS (SELECT 1 FROM sourcecut.odyssey_speeches_v AS s "
            f"WHERE s.book={book} AND s.line_start<={line_end} AND s.line_end>={line_start} "
            f"AND s.speaker_entity_id IN ({','.join(map(_sql_string, request.speaker_ids))}))"
        )
    if request.entity_ids:
        filters.append(
            "EXISTS (SELECT 1 FROM sourcecut.odyssey_entity_occurrences_v AS m "
            f"WHERE m.version_id={version} AND m.book={book} "
            f"AND m.line_start<={line_end} AND m.line_end>={line_start} "
            f"AND m.entity_id IN ({','.join(map(_sql_string, request.entity_ids))}))"
        )
    if request.narrative_levels:
        filters.append(
            "EXISTS (SELECT 1 FROM sourcecut.odyssey_event_passages_v AS e "
            f"WHERE e.version_id={version} AND e.book={book} "
            f"AND e.line_start<={line_end} AND e.line_end>={line_start} "
            f"AND e.narrative_level IN ({','.join(map(_sql_string, request.narrative_levels))}))"
        )
    return "".join(f" AND {item}" for item in filters)


def _default_search_versions(mode: SearchMode) -> tuple[str, ...]:
    if mode == SearchMode.ENGLISH:
        return ("odyssey-perseus-eng3", "odyssey-perseus-eng4")
    return ("odyssey-perseus-grc2",)


@dataclass(frozen=True, slots=True)
class ClickHouseMcpSettings:
    url: str = "http://127.0.0.1:8000/mcp"
    auth_token: str = ""
    timeout_seconds: float = 30.0
    allow_unauthenticated_local: bool = False
    max_result_rows: int = 500
    max_result_bytes: int = 2_000_000
    max_query_bytes: int = 32_768
    enforce_query_policy: bool = True

    @classmethod
    def from_env(cls) -> ClickHouseMcpSettings:
        settings = cls(
            url=os.getenv("CLICKHOUSE_MCP_URL", "http://127.0.0.1:8000/mcp"),
            auth_token=os.getenv("CLICKHOUSE_MCP_AUTH_TOKEN", ""),
            timeout_seconds=float(os.getenv("CLICKHOUSE_MCP_CLIENT_TIMEOUT", "30")),
            allow_unauthenticated_local=_env_bool("SOURCECUT_ALLOW_UNAUTHENTICATED_MCP", False),
            max_result_rows=int(os.getenv("CLICKHOUSE_MCP_MAX_RESULT_ROWS", "500")),
            max_result_bytes=int(os.getenv("CLICKHOUSE_MCP_MAX_RESULT_BYTES", "2000000")),
            max_query_bytes=int(os.getenv("CLICKHOUSE_MCP_MAX_QUERY_BYTES", "32768")),
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
        if not self.auth_token and not (is_loopback and self.allow_unauthenticated_local):
            raise ValueError(
                "CLICKHOUSE_MCP_AUTH_TOKEN is required; unauthenticated MCP is local-only"
            )
        if self.timeout_seconds <= 0:
            raise ValueError("CLICKHOUSE_MCP_CLIENT_TIMEOUT must be positive")
        if self.timeout_seconds > 60:
            raise ValueError("CLICKHOUSE_MCP_CLIENT_TIMEOUT cannot exceed 60 seconds")
        if self.max_result_rows <= 0 or self.max_result_rows > 5_000:
            raise ValueError("CLICKHOUSE_MCP_MAX_RESULT_ROWS must be between 1 and 5000")
        if self.max_result_bytes <= 0 or self.max_query_bytes <= 0:
            raise ValueError("MCP byte limits must be positive")

    @property
    def headers(self) -> dict[str, str] | None:
        if not self.auth_token:
            return None
        return {"Authorization": f"Bearer {self.auth_token}"}


class McpToolCallError(RuntimeError):
    pass


def validate_mcp_query(query: str, settings: ClickHouseMcpSettings) -> str | None:
    normalized = query.strip().rstrip(";").strip()
    if len(query.encode()) > settings.max_query_bytes:
        return "MCP query exceeds the configured byte limit"
    if not normalized or ";" in normalized or "--" in normalized or "/*" in normalized:
        return "MCP run_query accepts one comment-free statement"
    if not READ_QUERY_PATTERN.match(normalized):
        return "MCP run_query accepts only SELECT, WITH, or EXPLAIN"
    if UNSAFE_QUERY_PATTERN.search(normalized):
        return "MCP run_query rejected a mutating or settings-changing statement"
    limits = [int(value) for value in QUERY_LIMIT_PATTERN.findall(normalized)]
    if not limits or max(limits) > settings.max_result_rows:
        return f"MCP run_query requires every LIMIT to be <= {settings.max_result_rows}"
    return None


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
            if self._settings.enforce_query_policy:
                error = validate_mcp_query(query, self._settings)
                if error:
                    add_counter("sourcecut.mcp.rejected_queries", 1, {"reason": error})
                    raise ValueError(error)
            attributes["db.query.text"] = sanitize_sql(query)
            attributes["db.operation.name"] = "SELECT"
        started = time.perf_counter()
        try:
            with telemetry_span(f"clickhouse.mcp.{name}", attributes, kind=SpanKind.CLIENT) as span:
                async with self._session() as session:
                    result = await session.call_tool(name, arguments=arguments)
                payload = _decode_tool_result(result)
                returned_rows = _returned_rows(payload)
                result_bytes = len(json.dumps(payload, default=str).encode())
                if returned_rows > self._settings.max_result_rows:
                    raise McpToolCallError("MCP response exceeded the configured row limit")
                if result_bytes > self._settings.max_result_bytes:
                    raise McpToolCallError("MCP response exceeded the configured byte limit")
                span.set_attribute("db.response.returned_rows", returned_rows)
                span.set_attribute("db.response.size", result_bytes)
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
FROM sourcecut.passage_lookup(pid='{passage_id}')
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

    async def get_asset(self, asset_id: str) -> dict[str, Any]:
        if not ASSET_ID_PATTERN.fullmatch(asset_id):
            raise ValueError("asset_id contains unsupported characters")
        query = f"""
SELECT
    asset_id,
    provider,
    provider_id,
    title,
    description,
    creators,
    asset_type,
    creation_date_text,
    creation_year,
    subjects,
    places,
    source_url,
    media_url,
    thumbnail_path,
    rights_status,
    rights_text,
    historical_relationship,
    raw_metadata,
    metadata_sha256
FROM sourcecut.media_assets FINAL
WHERE asset_id = '{asset_id}'
LIMIT 2
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        if not rows:
            return {"status": "not_found", "asset_id": asset_id}
        if len(rows) > 1:
            raise RuntimeError(f"Duplicate asset_id in ClickHouse: {asset_id}")
        row = rows[0]
        asset = row if isinstance(row, dict) else dict(zip(columns, row, strict=True))
        return {"status": "found", "asset": _json_safe(asset)}

    async def get_classical_text(
        self, version_id: str, book: int, line_start: int, line_end: int
    ) -> dict[str, Any]:
        if not VERSION_ID_PATTERN.fullmatch(version_id):
            raise ValueError("Unknown Odyssey version")
        if not 1 <= book <= 24 or not 1 <= line_start <= line_end:
            raise ValueError("Invalid Odyssey text range")
        query = f"""
SELECT text_unit_id, citation, cts_urn, book, line_start, line_end, original_text
FROM sourcecut.odyssey_text_lookup_v
WHERE version_id = '{version_id}'
  AND book = {book}
  AND line_end >= {line_start}
  AND line_start <= {line_end}
ORDER BY line_start
LIMIT 200
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return {
            "version_id": version_id,
            "units": [
                _json_safe(row if isinstance(row, dict) else dict(zip(columns, row, strict=True)))
                for row in rows
            ],
        }

    async def get_parallel_classical_text(
        self,
        version_ids: list[str],
        book: int,
        line_start: int,
        line_end: int,
    ) -> list[dict[str, Any]]:
        return [
            await self.get_classical_text(version_id, book, line_start, line_end)
            for version_id in version_ids
        ]

    async def search_odyssey_text(
        self, request: TextSearchRequest, offset: int = 0
    ) -> dict[str, Any]:
        versions = request.version_ids or _default_search_versions(request.mode)
        if any(not VERSION_ID_PATTERN.fullmatch(item) for item in versions):
            raise ValueError("Unknown Odyssey version")
        if offset < 0 or offset > 100_000:
            raise ValueError("Search cursor is outside the allowed range")
        limit = request.page_size + 1
        if request.mode in {SearchMode.LEMMA, SearchMode.FORM, SearchMode.NORMALIZED}:
            if tuple(versions) != ("odyssey-perseus-grc2",):
                raise ValueError("Linguistic search is available for the pinned Greek edition")
            query_key = _accentless(request.query)
            field = "lemma_search" if request.mode == SearchMode.LEMMA else "accentless_surface"
            pos = (
                " AND t.part_of_speech IN ("
                + ",".join(_sql_string(item) for item in request.part_of_speech)
                + ")"
                if request.part_of_speech
                else ""
            )
            books = (
                f" AND t.book IN ({','.join(str(item) for item in request.books)})"
                if request.books
                else ""
            )
            annotations = _odyssey_annotation_filters(
                request, "t.version_id", "t.book", "t.line", "t.line"
            )
            query = f"""
SELECT token_id, text_unit_id, version_id, citation, cts_urn, book,
       line AS line_start, line AS line_end, original_text, surface, lemma,
       part_of_speech, morphology, char_start, char_end, annotation_source,
       annotation_confidence, review_status, annotation_version
FROM sourcecut.odyssey_lemma_occurrences_v AS t
WHERE t.{field} = {_sql_string(query_key)}{books}{pos}{annotations}
ORDER BY book, line, token_index
LIMIT {limit} OFFSET {offset}
""".strip()
        else:
            version_clause = ",".join(_sql_string(item) for item in versions)
            books = (
                f" AND u.book IN ({','.join(str(item) for item in request.books)})"
                if request.books
                else ""
            )
            annotations = _odyssey_annotation_filters(
                request, "u.version_id", "u.book", "u.line_start", "u.line_end"
            )
            predicate = (
                f"position(original_text, {_sql_string(request.query)}) > 0"
                if request.mode == SearchMode.EXACT
                else (
                    "positionCaseInsensitiveUTF8(casefolded_text, lowerUTF8("
                    f"{_sql_string(request.query)})) > 0"
                )
            )
            query = f"""
SELECT text_unit_id, version_id, citation, cts_urn, book, line_start, line_end, original_text
FROM sourcecut.odyssey_text_search_v AS u
WHERE u.version_id IN ({version_clause}){books}{annotations}
  AND {predicate}
ORDER BY version_id, book, line_start
LIMIT {limit} OFFSET {offset}
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return {
            "rows": _rows_json(columns, rows),
            "offset": offset,
        }

    async def get_odyssey_token(self, token_id: str) -> dict[str, Any]:
        if not TOKEN_ID_PATTERN.fullmatch(token_id):
            raise ValueError("Invalid Odyssey token ID")
        query = f"""
SELECT token_id, text_unit_id, version_id, citation, cts_urn, book, line,
       char_start, char_end, surface, lemma, part_of_speech, morphology, annotation_source,
       annotation_version, annotation_confidence, review_status,
       (SELECT count() FROM sourcecut.odyssey_lemma_occurrences_v o
        WHERE o.lemma_search = t.lemma_search) AS occurrence_count
FROM sourcecut.odyssey_lemma_occurrences_v AS t
WHERE token_id = {_sql_string(token_id)}
LIMIT 2
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return {"rows": _rows_json(columns, rows)}

    async def get_odyssey_frequency(self, request: FrequencyRequest) -> list[dict[str, Any]]:
        field = "lemma_search" if request.mode == "lemma" else "accentless_surface"
        joins = ""
        key = "toString(t.book)"
        if request.group_by == "speaker":
            joins = (
                "INNER JOIN sourcecut.odyssey_speeches_v AS s ON s.book=t.book "
                "AND s.line_start<=t.line AND s.line_end>=t.line"
            )
            key = "s.speaker_entity_id"
        elif request.group_by in {"scene", "narrative_level"}:
            joins = (
                "INNER JOIN sourcecut.odyssey_event_passages_v AS e ON e.book=t.book "
                "AND e.line_start<=t.line AND e.line_end>=t.line"
            )
            key = "e.event_id" if request.group_by == "scene" else "e.narrative_level"
        query = f"""
SELECT {key} AS key, count() AS count
FROM sourcecut.odyssey_lemma_occurrences_v AS t
{joins}
WHERE t.{field} = {_sql_string(_accentless(request.query))}
GROUP BY key
ORDER BY key
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_formulae(self, request: FormulaSearchRequest) -> list[dict[str, Any]]:
        filters = []
        if request.query:
            filters.append(
                f"position(normalized_formula, {_sql_string(_accentless(request.query))}) > 0"
            )
        if request.ngram_size is not None:
            filters.append(f"ngram_size = {request.ngram_size}")
        where = "WHERE " + " AND ".join(filters) if filters else ""
        query = f"""
SELECT formula_id, display_formula, normalized_formula, ngram_size,
       occurrence_count, occurrences
FROM sourcecut.odyssey_formula_occurrences_v
{where}
ORDER BY occurrence_count DESC, normalized_formula
LIMIT {request.page_size}
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_cooccurrences(self, request: CooccurrenceRequest) -> list[dict[str, Any]]:
        books = (
            f" AND a.book IN ({','.join(str(item) for item in request.books)})"
            if request.books
            else ""
        )
        query = f"""
SELECT a.book AS book, a.line AS left_line, b.line AS right_line,
       a.token_id AS left_token_id, b.token_id AS right_token_id,
       a.surface AS left_surface, b.surface AS right_surface,
       a.citation AS left_citation, b.citation AS right_citation
FROM sourcecut.odyssey_lemma_occurrences_v AS a
INNER JOIN sourcecut.odyssey_lemma_occurrences_v AS b
  ON a.book = b.book AND abs(toInt64(a.line) - toInt64(b.line)) <= {request.window_lines}
WHERE a.lemma_search = {_sql_string(_accentless(request.left_lemma))}
  AND b.lemma_search = {_sql_string(_accentless(request.right_lemma))}{books}
ORDER BY a.book, a.line, b.line
LIMIT 500
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_claim_source(self, source_record_id: str) -> dict[str, Any]:
        if not CLAIM_SOURCE_ID_PATTERN.fullmatch(source_record_id):
            raise ValueError("Invalid Odyssey claim source ID")
        query = f"""
SELECT text_unit_id, version_id, book, line_start, line_end, citation, cts_urn,
       original_text, normalized_text, text_sha256, source_document_id,
       source_version_hash, source_url, bibliographic_description, display_decision
FROM sourcecut.odyssey_claim_source_v
WHERE text_unit_id = {_sql_string(source_record_id)}
LIMIT 2
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return {"rows": _rows_json(columns, rows)}

    async def get_odyssey_scholarly_source(self, source_record_id: str) -> dict[str, Any]:
        if not CLAIM_SOURCE_ID_PATTERN.fullmatch(source_record_id):
            raise ValueError("Invalid Odyssey scholarly source ID")
        query = f"""
SELECT scholarly_source_id, source_type, title, creator_names, publication_year,
       publisher, doi, url, license_id, citation_text, metadata
FROM sourcecut.odyssey_scholarly_source_v
WHERE scholarly_source_id = {_sql_string(source_record_id)}
LIMIT 2
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return {"rows": _rows_json(columns, rows)}

    async def get_odyssey_timeline(
        self,
        *,
        mode: str,
        character_ids: list[str],
        place_ids: list[str],
        theme_ids: list[str],
        narrative_levels: list[str],
        books: list[int],
    ) -> list[dict[str, Any]]:
        if mode not in {"reading", "story"}:
            raise ValueError("Timeline mode must be reading or story")
        identifiers = character_ids + place_ids + theme_ids + narrative_levels
        if any(not NARRATIVE_ID_PATTERN.fullmatch(item) for item in identifiers):
            raise ValueError("Timeline filter contains unsupported characters")
        if any(book < 1 or book > 24 for book in books):
            raise ValueError("Timeline book filters must be between 1 and 24")
        filters = []
        if character_ids:
            filters.append(_array_overlap("participant_entity_ids", character_ids))
        if place_ids:
            filters.append(_array_overlap("place_ids", place_ids))
        if theme_ids:
            filters.append(_array_overlap("theme_ids", theme_ids))
        if narrative_levels:
            filters.append(
                "narrative_level IN (" + ",".join(map(_sql_string, narrative_levels)) + ")"
            )
        if books:
            filters.append("arrayExists(p -> p.2 IN (" + ",".join(map(str, books)) + "), passages)")
        where = "WHERE " + " AND ".join(filters) if filters else ""
        order = "reading_order_start" if mode == "reading" else "story_order_start"
        query = f"""
SELECT event_id, title, summary, event_type, reading_order_start, reading_order_end,
       story_order_start, story_order_end, duration_value, duration_unit,
       duration_certainty, duration_source_note, narrative_level, narrator_entity_id,
       participant_entity_ids, place_ids, theme_ids, parent_event_id, passages
FROM sourcecut.odyssey_event_timeline_v
{where}
ORDER BY {order}, event_id
LIMIT 500
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_event(self, event_id: str) -> list[dict[str, Any]]:
        if not NARRATIVE_ID_PATTERN.fullmatch(event_id):
            raise ValueError("Invalid Odyssey event ID")
        query = f"""
SELECT event_id, title, summary, event_type, reading_order_start, reading_order_end,
       story_order_start, story_order_end, duration_value, duration_unit,
       duration_certainty, duration_source_note, narrative_level, narrator_entity_id,
       participant_entity_ids, place_ids, theme_ids, parent_event_id, passages
FROM sourcecut.odyssey_event_timeline_v
WHERE event_id = {_sql_string(event_id)}
LIMIT 2
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_speeches(
        self, speaker_ids: list[str], books: list[int]
    ) -> list[dict[str, Any]]:
        if any(not NARRATIVE_ID_PATTERN.fullmatch(item) for item in speaker_ids):
            raise ValueError("Invalid speaker filter")
        if any(book < 1 or book > 24 for book in books):
            raise ValueError("Speech book filters must be between 1 and 24")
        filters = []
        if speaker_ids:
            filters.append("speaker_entity_id IN (" + ",".join(map(_sql_string, speaker_ids)) + ")")
        if books:
            filters.append("book IN (" + ",".join(map(str, books)) + ")")
        where = "WHERE " + " AND ".join(filters) if filters else ""
        query = f"""
SELECT speech_id, speaker_entity_id, addressee_entity_ids, audience_entity_ids,
       narrator_entity_id, narrative_level, book, line_start, line_end, speech_type
FROM sourcecut.odyssey_speeches_v
{where}
ORDER BY book, line_start, speech_id
LIMIT 500
""".strip()
        payload = await self.call_tool("run_query", {"query": query})
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_route_graph(self) -> dict[str, list[dict[str, Any]]]:
        nodes_payload = await self.call_tool(
            "run_query",
            {
                "query": """
SELECT n.route_node_id, n.hypothesis_id, n.event_id, n.poetic_place_id,
       p.canonical_name, p.place_class, n.sequence_index, n.node_kind,
       n.longitude, n.latitude, n.display_region, n.citation_ids
FROM sourcecut.route_nodes FINAL AS n
INNER JOIN sourcecut.poetic_places FINAL AS p ON p.poetic_place_id = n.poetic_place_id
WHERE n.hypothesis_id = 'textual_sequence' AND n.review_status = 'trusted'
ORDER BY n.sequence_index LIMIT 200
""".strip()
            },
        )
        edges_payload = await self.call_tool(
            "run_query",
            {
                "query": """
SELECT route_edge_id, hypothesis_id, from_node_id, to_node_id, edge_kind,
       sequence_index, certainty, citation_ids
FROM sourcecut.route_edges FINAL
WHERE hypothesis_id = 'textual_sequence' AND review_status = 'trusted'
ORDER BY sequence_index LIMIT 200
""".strip()
            },
        )
        node_columns, node_rows = _query_rows(nodes_payload)
        edge_columns, edge_rows = _query_rows(edges_payload)
        return {
            "nodes": _rows_json(node_columns, node_rows),
            "edges": _rows_json(edge_columns, edge_rows),
        }

    async def get_odyssey_map_features(
        self, hypothesis_ids: list[str], classes: list[str]
    ) -> list[dict[str, Any]]:
        if len(hypothesis_ids) > 3:
            raise ValueError("At most three route hypotheses may be compared")
        if any(not NARRATIVE_ID_PATTERN.fullmatch(item) for item in hypothesis_ids + classes):
            raise ValueError("Invalid map filter")
        filters = []
        if hypothesis_ids:
            filters.append("hypothesis_id IN (" + ",".join(map(_sql_string, hypothesis_ids)) + ")")
        if classes:
            filters.append("identification_class IN (" + ",".join(map(_sql_string, classes)) + ")")
        where = "WHERE " + " AND ".join(filters) if filters else ""
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT identification_id, poetic_place_id, canonical_name, place_class,
       hypothesis_id, identification_class, longitude, latitude, confidence,
       status, rationale, scholarly_source_ids
FROM sourcecut.odyssey_map_features_v
{where}
ORDER BY hypothesis_id, poetic_place_id LIMIT 500
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_route_hypotheses(self, hypothesis_id: str = "") -> list[dict[str, Any]]:
        if hypothesis_id and not NARRATIVE_ID_PATTERN.fullmatch(hypothesis_id):
            raise ValueError("Invalid route hypothesis ID")
        where = (
            f"WHERE hypothesis_id = {_sql_string(hypothesis_id)} AND "
            if hypothesis_id
            else "WHERE "
        )
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT hypothesis_id, title, author_or_tradition, description, scholarly_source_ids,
       license_id, display_order, is_default
FROM sourcecut.route_hypotheses FINAL
{where}review_status = 'trusted'
ORDER BY display_order LIMIT 20
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_poetic_place(self, poetic_place_id: str) -> list[dict[str, Any]]:
        if not NARRATIVE_ID_PATTERN.fullmatch(poetic_place_id):
            raise ValueError("Invalid poetic place ID")
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT identification_id, poetic_place_id, canonical_name, place_class,
       hypothesis_id, identification_class, longitude, latitude, confidence,
       status, rationale, scholarly_source_ids
FROM sourcecut.odyssey_map_features_v
WHERE poetic_place_id = {_sql_string(poetic_place_id)}
ORDER BY hypothesis_id LIMIT 20
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def list_odyssey_entities(self) -> list[dict[str, Any]]:
        payload = await self.call_tool(
            "run_query",
            {
                "query": """
SELECT entity_id, entity_type, canonical_name, greek_name, aliases, description,
       authority_uris, curation_citations, countIf(notEmpty(mention_id)) AS occurrence_count
FROM sourcecut.odyssey_entity_occurrences_v
GROUP BY entity_id, entity_type, canonical_name, greek_name, aliases, description,
         authority_uris, curation_citations
ORDER BY entity_type, canonical_name LIMIT 500
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_entity(self, entity_id: str) -> list[dict[str, Any]]:
        if not NARRATIVE_ID_PATTERN.fullmatch(entity_id):
            raise ValueError("Invalid classical entity ID")
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT entity_id, entity_type, canonical_name, greek_name, aliases, description,
       authority_uris, curation_citations, mention_id, text_unit_id, version_id,
       book, line_start, line_end, surface, char_start, char_end, mention_role,
       confidence, citation, cts_urn, original_text
FROM sourcecut.odyssey_entity_occurrences_v
WHERE entity_id = {_sql_string(entity_id)}
ORDER BY version_id, book, line_start LIMIT 500
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_relationships(self, entity_id: str = "") -> list[dict[str, Any]]:
        if entity_id and not NARRATIVE_ID_PATTERN.fullmatch(entity_id):
            raise ValueError("Invalid classical entity ID")
        entity_filter = (
            f" AND (a.entity_id = {_sql_string(entity_id)} "
            f"OR b.entity_id = {_sql_string(entity_id)})"
            if entity_id
            else ""
        )
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT a.entity_id AS source_entity_id, b.entity_id AS target_entity_id,
       any(a.entity_type) AS source_type, any(b.entity_type) AS target_type,
       count() AS shared_unit_count, groupUniqArray(20)(a.text_unit_id) AS evidence_unit_ids
FROM sourcecut.odyssey_entity_occurrences_v AS a
INNER JOIN sourcecut.odyssey_entity_occurrences_v AS b
  ON a.text_unit_id = b.text_unit_id AND a.entity_id < b.entity_id
WHERE notEmpty(a.mention_id) AND notEmpty(b.mention_id){entity_filter}
GROUP BY a.entity_id, b.entity_id
ORDER BY shared_unit_count DESC LIMIT 300
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        result = _rows_json(columns, rows)
        for row in result:
            row["relationship_kind"] = "exact_unit_cooccurrence"
            row["interpretation_notice"] = (
                "Retrieval aid only; co-occurrence is not evidence of a historical relationship."
            )
        return result

    async def list_odyssey_themes(self) -> list[dict[str, Any]]:
        payload = await self.call_tool(
            "run_query",
            {
                "query": """
SELECT theme_id, title, description, aliases, bibliography, curator,
       countIf(notEmpty(theme_passage_id)) AS passage_count
FROM sourcecut.odyssey_theme_passages_v
GROUP BY theme_id, title, description, aliases, bibliography, curator
ORDER BY title LIMIT 100
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_theme(self, theme_id: str) -> list[dict[str, Any]]:
        if not NARRATIVE_ID_PATTERN.fullmatch(theme_id):
            raise ValueError("Invalid Odyssey theme ID")
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT theme_id, title, description, aliases, bibliography, curator,
       theme_passage_id, rationale, evidence_class, text_unit_id, version_id,
       book, line_start, line_end, citation, cts_urn, original_text
FROM sourcecut.odyssey_theme_passages_v
WHERE theme_id = {_sql_string(theme_id)}
ORDER BY book, line_start LIMIT 500
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def search_odyssey_assets(
        self,
        query_text: str,
        relationships: list[str],
        public_only: bool,
        facets: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        if query_text:
            filters.append(
                "positionCaseInsensitiveUTF8(concat(title,' ',description,' ',culture,' ',medium), "
                f"{_sql_string(query_text)}) > 0"
            )
        if relationships:
            filters.append(
                "relationship_class IN (" + ",".join(map(_sql_string, relationships)) + ")"
            )
        if public_only:
            filters.extend(["public_display = true", "verification_status != 'rejected'"])
        selected = facets or {}
        for field, key in (
            ("provider", "providers"),
            ("rights_status", "rights"),
            ("culture", "cultures"),
            ("medium", "media"),
        ):
            values = selected.get(key) or []
            if values:
                filters.append(f"{field} IN ({','.join(map(_sql_string, values))})")
        if selected.get("image_available") is not None:
            filters.append(
                "notEmpty(cached_image_path)"
                if selected["image_available"]
                else "empty(cached_image_path)"
            )
        if selected.get("target_kind") and selected.get("target_id"):
            filters.append(
                "arrayExists(link -> link.1 = "
                f"{_sql_string(selected['target_kind'])} AND link.2 = "
                f"{_sql_string(selected['target_id'])}, corpus_links)"
            )
        where = "WHERE " + " AND ".join(filters) if filters else ""
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT asset_id, provider, provider_id, title, description, creators, asset_type,
       creation_date_text, subjects, source_url, rights_status, rights_text,
       institution, object_id, culture, period, object_date, object_begin_date,
       object_end_date, medium, image_rights_status, image_attribution,
       cached_image_path, public_display, relationship_class, production_use,
       limitations, evidence_ids, confidence, verification_status, corpus_links
FROM sourcecut.odyssey_visual_assets_v
{where}
ORDER BY object_begin_date, title LIMIT 300
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)

    async def get_odyssey_visual_asset(self, asset_id: str) -> list[dict[str, Any]]:
        if not ASSET_ID_PATTERN.fullmatch(asset_id):
            raise ValueError("Invalid visual asset ID")
        payload = await self.call_tool(
            "run_query",
            {
                "query": f"""
SELECT asset_id, provider, provider_id, title, description, creators, asset_type,
       creation_date_text, subjects, source_url, rights_status, rights_text,
       institution, object_id, culture, period, object_date, object_begin_date,
       object_end_date, medium, image_rights_status, image_attribution,
       cached_image_path, public_display, relationship_class, production_use,
       limitations, evidence_ids, confidence, verification_status, corpus_links
FROM sourcecut.odyssey_visual_assets_v
WHERE asset_id = {_sql_string(asset_id)} LIMIT 2
""".strip()
            },
        )
        columns, rows = _query_rows(payload)
        return _rows_json(columns, rows)


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
    parameterized_views_reached: bool
    vector_query_reached: bool
    term_dictionary_reached: bool
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
    client = ClickHouseMcpClient(replace(resolved, enforce_query_policy=False))
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
                "SELECT count() AS passages FROM sourcecut.passages FINAL "
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
    author_id,
    author_display_name,
    mention_count,
    passage_ids
FROM sourcecut.author_term_presence(
    start=18050909,
    end=18050930,
    term='snow'
)
ORDER BY author_display_name
LIMIT 10
""".strip()
        },
    )
    evidence_columns, evidence_rows = _query_rows(evidence_payload)
    visual_evidence_authors = sum(
        1 for row in evidence_rows if int(row[evidence_columns.index("mention_count")]) > 0
    )
    wagon_payload = await client.call_tool(
        "run_query",
        {
            "query": """
SELECT author_display_name, mention_count
FROM sourcecut.author_term_presence(
    start=18050909,
    end=18050930,
    term='wagon'
)
ORDER BY author_display_name
LIMIT 10
""".strip()
        },
    )
    wagon_columns, wagon_rows = _query_rows(wagon_payload)
    wagon_mentions = sum(int(row[wagon_columns.index("mention_count")]) for row in wagon_rows)
    window_payload = await client.call_tool(
        "run_query",
        {
            "query": """
SELECT count() AS rows
FROM sourcecut.evidence_window(start=18050909, end=18050930, limit=1)
LIMIT 1
""".strip()
        },
    )
    window_columns, window_rows = _query_rows(window_payload)
    matrix_payload = await client.call_tool(
        "run_query",
        {
            "query": """
SELECT count() AS rows
FROM sourcecut.author_date_matrix(
    terms=['snow', 'snowing'], start=18050909, end=18050930
)
LIMIT 1
""".strip()
        },
    )
    matrix_columns, matrix_rows = _query_rows(matrix_payload)
    parameterized_views_reached = (
        bool(window_rows)
        and "rows" in window_columns
        and bool(matrix_rows)
        and "rows" in matrix_columns
    )
    vector_payload = await client.call_tool(
        "run_query",
        {"query": ("SELECT cosineDistance([1.0, 0.0], [1.0, 0.0]) AS distance LIMIT 1")},
    )
    vector_columns, vector_rows = _query_rows(vector_payload)
    vector_query_reached = (
        bool(vector_rows) and float(vector_rows[0][vector_columns.index("distance")]) == 0.0
    )
    dictionary_payload = await client.call_tool(
        "run_query",
        {
            "query": (
                "SELECT dictGet('sourcecut.term_expansion_dict', 'expansions', "
                "tuple('equipment', 'moccasin')) AS expansions LIMIT 1"
            )
        },
    )
    dictionary_columns, dictionary_rows = _query_rows(dictionary_payload)
    term_dictionary_reached = (
        "mocassons" in dictionary_rows[0][dictionary_columns.index("expansions")]
    )

    snow_payload = await client.call_tool(
        "run_query",
        {
            "query": """
SELECT passage_id
FROM sourcecut.passages FINAL
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
                    "SELECT count() FROM sourcecut.passages FINAL LIMIT 1 "
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
        raise RuntimeError(f"Unauthenticated MCP request returned HTTP {unauthenticated_status}")
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
        parameterized_views_reached=parameterized_views_reached,
        vector_query_reached=vector_query_reached,
        term_dictionary_reached=term_dictionary_reached,
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
    text_blocks = [block.text for block in result.content if getattr(block, "type", None) == "text"]
    if not text_blocks:
        return None
    text = "\n".join(text_blocks)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def query_rows(payload: Any) -> tuple[list[str], list[Any]]:
    """Decode a run_query payload into (columns, rows). Public API surface."""
    if not isinstance(payload, dict):
        raise RuntimeError("ClickHouse MCP run_query returned an unexpected payload")
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise RuntimeError("ClickHouse MCP run_query omitted columns or rows")
    return [str(column) for column in columns], rows


_query_rows = query_rows


def _rows_json(columns: list[str], rows: list[Any]) -> list[dict[str, Any]]:
    return [
        _json_safe(row if isinstance(row, dict) else dict(zip(columns, row, strict=True)))
        for row in rows
    ]


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


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
