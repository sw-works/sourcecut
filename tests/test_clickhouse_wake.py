"""A suspended ClickHouse Cloud service is a pause, not an answer."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from sourcecut_api.db import client as client_module
from sourcecut_api.db.wake import is_wake_error, wake_delays
from sourcecut_api.integrations.clickhouse_mcp import ClickHouseMcpClient, ClickHouseMcpSettings


@pytest.mark.parametrize(
    "message",
    [
        "Service is not running",
        "HTTPDriver for https://x.clickhouse.cloud:8443 returned response code 503",
        "Connection refused",
        "Read timed out",
        "Server disconnected without sending a response",
        "Temporary failure in name resolution",
    ],
)
def test_wake_shapes_are_worth_another_attempt(message: str) -> None:
    assert is_wake_error(message)


@pytest.mark.parametrize(
    "message",
    [
        "Code: 47. DB::Exception: Unknown expression identifier 'passge_text'",
        "Code: 497. DB::Exception: not enough privileges on table evidence",
        "MCP response exceeded the configured row limit",
        "MCP run_query requires every LIMIT to be <= 200",
    ],
)
def test_real_answers_are_not_retried(message: str) -> None:
    assert not is_wake_error(message)


def test_delays_lengthen_so_a_slow_resume_is_still_caught() -> None:
    assert list(wake_delays(retries=3, backoff=1.5)) == [1.5, 3.0, 6.0]
    assert list(wake_delays(retries=0, backoff=1.5)) == []


def test_connection_retries_through_a_wake(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def flaky(**_: object) -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("Connection refused")
        return "client"

    monkeypatch.setattr(client_module.clickhouse_connect, "get_client", flaky)
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setenv("CLICKHOUSE_WAKE_BACKOFF_SECONDS", "0.01")

    assert client_module.create_clickhouse_client() == "client"
    assert len(attempts) == 3


def test_connection_raises_a_real_error_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def refused(**_: object) -> str:
        attempts.append(1)
        raise ValueError("Code: 516. DB::Exception: Authentication failed")

    monkeypatch.setattr(client_module.clickhouse_connect, "get_client", refused)
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(ValueError):
        client_module.create_clickhouse_client()
    assert len(attempts) == 1


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


def _mcp_client() -> ClickHouseMcpClient:
    return ClickHouseMcpClient(
        ClickHouseMcpSettings(url="http://127.0.0.1:8000/mcp", auth_token="token")
    )


@pytest.mark.anyio
async def test_mcp_call_retries_while_the_service_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _mcp_client()
    monkeypatch.setenv("CLICKHOUSE_WAKE_BACKOFF_SECONDS", "0.01")

    async def sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("sourcecut_api.integrations.clickhouse_mcp.asyncio.sleep", sleep)

    calls: list[int] = []

    class _Session:
        async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
            calls.append(1)
            if len(calls) < 2:
                raise ConnectionError("Server disconnected without sending a response")
            return _Result()

    class _Result:
        isError = False
        structuredContent = {"result": '[{"passage_text": "text"}]'}
        content: tuple[object, ...] = ()

    @asynccontextmanager
    async def session():  # type: ignore[no-untyped-def]
        yield _Session()

    monkeypatch.setattr(client, "_session", session)
    span = _Span()
    payload = await client._call_through_wake("run_query", {"query": "SELECT 1"}, span)
    assert payload == [{"passage_text": "text"}]
    assert len(calls) == 2
    assert span.attributes["sourcecut.mcp.wake_retries"] == 1
