"""ADK hooks that turn one agent run into the timeline the user watches.

The research surface already streams `research_events` over SSE; until now only
the deterministic board service wrote to it, so an ADK run was a black box that
printed to a terminal. This module registers one ADK **plugin** on the runner,
which is the only hook point that sees every sub-agent in a `SequentialAgent`
without each agent having to opt in.

The plugin is strictly an observer. Every hook returns ``None``, because a
non-``None`` return from `before_tool_callback` skips the tool and from
`before_model_callback` skips the model call — an event writer must never be
able to change what the agent does. The query guardrail stays where it is, on
the agent's own `before_tool_callback`; plugin hooks run first, so a blocked
query still reports as started and then as blocked.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from sourcecut_api.telemetry import sanitize_sql

# (event_type, stage, status, message, payload, duration_ms) — the signature
# ResearchBoardService.event_sink already uses, so the same sink serves both.
ActivitySink = Callable[[str, str, str, str, dict[str, Any], int], None]

MCP_TOOLS = frozenset({"list_databases", "list_tables", "run_query"})
#: Longest tool result echoed into an event payload. Timeline events are read by
#: a human, not replayed; the full result is already in the ClickHouse row.
PREVIEW_LIMIT = 400


class ActivityStreamPlugin(BasePlugin):
    """Emit one timeline event per agent, model call and tool call.

    Register on the runner, not on an agent::

        runner = InMemoryRunner(
            agent=runtime.agent,
            app_name="sourcecut",
            plugins=[ActivityStreamPlugin(sink=sink)],
        )
    """

    def __init__(self, *, sink: ActivitySink, name: str = "sourcecut_activity") -> None:
        super().__init__(name=name)
        self._sink = sink
        self._started_ns: dict[str, int] = {}

    # -- run ---------------------------------------------------------------

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        self._mark(f"run:{invocation_context.invocation_id}")
        self._emit(
            "agent_run_started",
            "agent",
            "active",
            "ADK research run started.",
            {"agent": invocation_context.agent.name},
        )
        return None

    async def after_run_callback(self, *, invocation_context: InvocationContext) -> None:
        self._emit(
            "agent_run_completed",
            "agent",
            "complete",
            "ADK research run finished.",
            {"agent": invocation_context.agent.name},
            self._elapsed_ms(f"run:{invocation_context.invocation_id}"),
        )
        return None

    # -- agents ------------------------------------------------------------

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        self._mark(f"agent:{callback_context.invocation_id}:{agent.name}")
        self._emit(
            "stage_started",
            agent.name,
            "active",
            f"{_readable(agent.name)} started.",
            {"agent": agent.name, "description": agent.description},
        )
        return None

    async def after_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        self._emit(
            "stage_completed",
            agent.name,
            "complete",
            f"{_readable(agent.name)} finished.",
            {"agent": agent.name},
            self._elapsed_ms(f"agent:{callback_context.invocation_id}:{agent.name}"),
        )
        return None

    # -- model calls -------------------------------------------------------

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> None:
        self._mark(f"model:{callback_context.invocation_id}:{callback_context.agent_name}")
        self._emit(
            "model_request",
            callback_context.agent_name,
            "active",
            f"{_readable(callback_context.agent_name)} is thinking.",
            {
                "model": llm_request.model or "",
                "tools_available": sorted(llm_request.tools_dict or {}),
                "history_turns": len(llm_request.contents or ()),
            },
        )
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> None:
        # Streaming delivers a response object per chunk. Only the final one
        # carries a usable finish reason, and only it should reach the timeline.
        if llm_response.partial:
            return None
        calls = [
            part.function_call.name
            for part in (llm_response.content.parts if llm_response.content else ())
            if part.function_call is not None and part.function_call.name
        ]
        payload: dict[str, Any] = {
            "agent": callback_context.agent_name,
            "tool_calls_requested": calls,
        }
        usage = llm_response.usage_metadata
        if usage is not None:
            payload["input_tokens"] = usage.prompt_token_count or 0
            payload["output_tokens"] = usage.candidates_token_count or 0
        failed = bool(llm_response.error_code)
        if failed:
            payload["error_code"] = str(llm_response.error_code)
        self._emit(
            "model_response",
            callback_context.agent_name,
            "failed" if failed else "complete",
            _model_message(callback_context.agent_name, calls, failed),
            payload,
            self._elapsed_ms(f"model:{callback_context.invocation_id}:{callback_context.agent_name}"),
        )
        return None

    async def on_model_error_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
        error: Exception,
    ) -> None:
        del llm_request
        self._emit(
            "model_failed",
            callback_context.agent_name,
            "failed",
            f"{_readable(callback_context.agent_name)} could not reach the model.",
            {"error_type": type(error).__name__},
            self._elapsed_ms(f"model:{callback_context.invocation_id}:{callback_context.agent_name}"),
        )
        return None

    # -- tool calls --------------------------------------------------------

    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext
    ) -> None:
        self._mark(_tool_key(tool, tool_context))
        payload: dict[str, Any] = {
            "tool": tool.name,
            "agent": tool_context.agent_name,
            "access_path": _access_path(tool.name),
        }
        payload.update(_tool_arguments(tool_args))
        self._emit(
            "tool_started",
            tool_context.agent_name,
            "active",
            f"Calling {tool.name}.",
            payload,
        )
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> None:
        blocked = _blocked_reason(result)
        payload: dict[str, Any] = {
            "tool": tool.name,
            "agent": tool_context.agent_name,
            "access_path": _access_path(tool.name),
        }
        payload.update(_tool_arguments(tool_args))
        if blocked is not None:
            payload["reason"] = blocked
            self._emit(
                "tool_blocked",
                tool_context.agent_name,
                "failed",
                f"{tool.name} was refused: {blocked}",
                payload,
                self._elapsed_ms(_tool_key(tool, tool_context)),
            )
            return None
        preview = _result_preview(result)
        if preview is not None:
            payload["preview"] = preview
        self._emit(
            "tool_completed",
            tool_context.agent_name,
            "complete",
            f"{tool.name} returned.",
            payload,
            self._elapsed_ms(_tool_key(tool, tool_context)),
        )
        return None

    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> None:
        del tool_args
        self._emit(
            "tool_failed",
            tool_context.agent_name,
            "failed",
            f"{tool.name} raised {type(error).__name__}.",
            {
                "tool": tool.name,
                "agent": tool_context.agent_name,
                "error_type": type(error).__name__,
            },
            self._elapsed_ms(_tool_key(tool, tool_context)),
        )
        return None

    # -- plumbing ----------------------------------------------------------

    def _mark(self, key: str) -> None:
        self._started_ns[key] = time.perf_counter_ns()

    def _elapsed_ms(self, key: str) -> int:
        started = self._started_ns.pop(key, None)
        if started is None:
            return 0
        return int((time.perf_counter_ns() - started) / 1_000_000)

    def _emit(
        self,
        event_type: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any],
        duration_ms: int = 0,
    ) -> None:
        # A timeline is feedback, never the run. A sink that fails — ClickHouse
        # unreachable, a closed stream — must not take the research down with it.
        try:
            self._sink(event_type, stage, status, message, payload, duration_ms)
        except Exception:  # noqa: BLE001 - deliberate: see comment above
            pass


def _tool_key(tool: BaseTool, tool_context: ToolContext) -> str:
    # Parallel function calls share an agent and a tool name, so the call id is
    # what keeps two concurrent run_query timings apart.
    return f"tool:{tool_context.function_call_id or tool_context.invocation_id}:{tool.name}"


def _access_path(tool_name: str) -> str:
    return "mcp_runtime" if tool_name in MCP_TOOLS else "deterministic"


def _tool_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Only arguments a reader can act on, and SQL only in sanitized form."""
    selected: dict[str, Any] = {}
    query = args.get("query")
    if isinstance(query, str):
        selected["sql"] = sanitize_sql(query)
    passage_id = args.get("passage_id")
    if isinstance(passage_id, str):
        selected["passage_id"] = passage_id
    return selected


def _blocked_reason(result: Any) -> str | None:
    """The guardrail's refusal, told apart from a tool that ran and returned."""
    if isinstance(result, dict):
        error = result.get("error")
        if isinstance(error, str) and error:
            return error
    return None


def _result_preview(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    structured = result.get("structuredContent")
    raw = structured.get("result") if isinstance(structured, dict) else None
    if isinstance(raw, str) and raw:
        return raw[:PREVIEW_LIMIT]
    return None


def _model_message(agent_name: str, calls: list[str], failed: bool) -> str:
    who = _readable(agent_name)
    if failed:
        return f"{who} received a model error."
    if calls:
        return f"{who} asked for {', '.join(sorted(set(calls)))}."
    return f"{who} answered."


def _readable(agent_name: str) -> str:
    return agent_name.replace("sourcecut_", "").replace("_", " ").capitalize()
