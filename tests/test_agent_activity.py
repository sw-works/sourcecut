from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from sourcecut_api.agents.activity import ActivityStreamPlugin


@dataclass
class Recorder:
    events: list[tuple[str, str, str, str, dict[str, Any], int]] = field(
        default_factory=list
    )

    def __call__(self, *event: Any) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [event[0] for event in self.events]

    def find(self, event_type: str) -> tuple[str, str, str, str, dict[str, Any], int]:
        return next(event for event in self.events if event[0] == event_type)


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


@dataclass
class FakeToolContext:
    agent_name: str = "sourcecut_evidence"
    invocation_id: str = "invocation-1"
    function_call_id: str | None = "call-1"


@dataclass
class FakeCallbackContext:
    agent_name: str = "sourcecut_evidence"
    invocation_id: str = "invocation-1"


@dataclass
class FakeAgent:
    name: str = "sourcecut_planner"
    description: str = "Decides the window"


def plugin() -> tuple[ActivityStreamPlugin, Recorder]:
    sink = Recorder()
    return ActivityStreamPlugin(sink=sink), sink


def test_tool_call_reports_started_and_completed_with_sanitized_sql() -> None:
    hooks, sink = plugin()
    tool = FakeTool("run_query")
    context = FakeToolContext()
    args = {
        "query": (
            "SELECT passage_id FROM sourcecut.passages FINAL "
            "WHERE entry_date = 18050916 LIMIT 5"
        )
    }

    asyncio.run(hooks.before_tool_callback(tool=tool, tool_args=args, tool_context=context))
    asyncio.run(
        hooks.after_tool_callback(
            tool=tool,
            tool_args=args,
            tool_context=context,
            result={"structuredContent": {"result": '{"rows": [[1]]}'}},
        )
    )

    assert sink.types() == ["tool_started", "tool_completed"]
    started = sink.find("tool_started")
    assert started[4]["access_path"] == "mcp_runtime"
    # Literals never reach the timeline, even from a query the guardrail allowed.
    assert "18050916" not in started[4]["sql"]
    assert sink.find("tool_completed")[4]["preview"] == '{"rows": [[1]]}'


def test_a_refused_query_reports_as_blocked_with_the_reason() -> None:
    hooks, sink = plugin()
    tool = FakeTool("run_query")
    context = FakeToolContext()
    reason = "run_query requires a literal LIMIT no greater than 200"

    asyncio.run(
        hooks.after_tool_callback(
            tool=tool,
            tool_args={"query": "SELECT 1"},
            tool_context=context,
            result={"error": reason},
        )
    )

    event_type, _, status, message, payload, _ = sink.find("tool_blocked")
    assert (event_type, status) == ("tool_blocked", "failed")
    assert payload["reason"] == reason
    assert reason in message


def test_every_hook_returns_none_so_it_cannot_alter_the_run() -> None:
    """A non-None return would skip the tool or the model call outright."""
    hooks, _ = plugin()
    tool = FakeTool("run_query")
    context = FakeToolContext()

    before = asyncio.run(
        hooks.before_tool_callback(tool=tool, tool_args={}, tool_context=context)
    )
    after = asyncio.run(
        hooks.after_tool_callback(
            tool=tool, tool_args={}, tool_context=context, result={"error": "no"}
        )
    )
    agent = asyncio.run(
        hooks.before_agent_callback(agent=FakeAgent(), callback_context=FakeCallbackContext())
    )
    assert (before, after, agent) == (None, None, None)


def test_a_failing_sink_does_not_reach_the_agent() -> None:
    def explode(*event: Any) -> None:
        raise RuntimeError("ClickHouse is unreachable")

    hooks = ActivityStreamPlugin(sink=explode)
    asyncio.run(
        hooks.before_agent_callback(agent=FakeAgent(), callback_context=FakeCallbackContext())
    )


def test_agent_stage_events_name_the_specialist() -> None:
    hooks, sink = plugin()
    agent = FakeAgent(name="sourcecut_auditor", description="Checks citations")
    context = FakeCallbackContext(agent_name="sourcecut_auditor")

    asyncio.run(hooks.before_agent_callback(agent=agent, callback_context=context))
    asyncio.run(hooks.after_agent_callback(agent=agent, callback_context=context))

    started = sink.find("stage_started")
    assert started[1] == "sourcecut_auditor"
    assert started[3] == "Auditor started."
    assert sink.find("stage_completed")[2] == "complete"


def test_partial_model_responses_are_not_reported() -> None:
    hooks, sink = plugin()
    context = FakeCallbackContext()

    class Partial:
        partial = True

    asyncio.run(hooks.after_model_callback(callback_context=context, llm_response=Partial()))
    assert sink.events == []


def test_a_model_response_reports_the_tools_it_asked_for() -> None:
    hooks, sink = plugin()
    context = FakeCallbackContext()

    class Call:
        name = "run_query"

    class Part:
        function_call = Call()

    class Content:
        parts = [Part()]

    class Response:
        partial = False
        content = Content()
        usage_metadata = None
        error_code = None

    asyncio.run(hooks.after_model_callback(callback_context=context, llm_response=Response()))

    _, _, status, message, payload, _ = sink.find("model_response")
    assert status == "complete"
    assert payload["tool_calls_requested"] == ["run_query"]
    assert message == "Evidence asked for run_query."


def test_a_registered_plugin_is_driven_by_the_adk_runner() -> None:
    """The hooks are only useful if ADK actually calls them: prove it end to end.

    A stub agent stands in for the research pipeline so this runs with no Gemini
    credential and no MCP server; what is under test is the wiring, not the model.
    """
    from collections.abc import AsyncGenerator

    from google.adk.agents.base_agent import BaseAgent
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.apps import App
    from google.adk.events.event import Event
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    class StubAgent(BaseAgent):
        async def _run_async_impl(
            self, ctx: InvocationContext
        ) -> AsyncGenerator[Event, None]:
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text="done")]),
            )

    sink = Recorder()
    runner = InMemoryRunner(
        app=App(
            name="sourcecut",
            root_agent=StubAgent(name="sourcecut_stub", description="stands in"),
            plugins=[ActivityStreamPlugin(sink=sink)],
        )
    )

    async def run() -> None:
        await runner.session_service.create_session(
            app_name="sourcecut", user_id="test", session_id="session-1"
        )
        async for _ in runner.run_async(
            user_id="test",
            session_id="session-1",
            new_message=types.Content(role="user", parts=[types.Part(text="hello")]),
        ):
            pass
        await runner.close()

    asyncio.run(run())

    assert sink.types() == [
        "agent_run_started",
        "stage_started",
        "stage_completed",
        "agent_run_completed",
    ]
    assert sink.find("stage_started")[1] == "sourcecut_stub"
