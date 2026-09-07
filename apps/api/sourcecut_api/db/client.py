from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import clickhouse_connect

from sourcecut_api.db.wake import is_wake_error, wake_delays

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of true/false, 1/0, yes/no, or on/off")


@dataclass(frozen=True, slots=True)
class ClickHouseSettings:
    host: str = "localhost"
    port: int = 8123
    username: str = "default"
    password: str = ""
    database: str = "default"
    secure: bool = False
    connect_timeout_seconds: int = 10
    send_receive_timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> ClickHouseSettings:
        secure = _env_bool("CLICKHOUSE_SECURE", False)
        default_port = 8443 if secure else 8123
        return cls(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", str(default_port))),
            username=os.getenv("CLICKHOUSE_USERNAME", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DATABASE", "default"),
            secure=secure,
            connect_timeout_seconds=int(os.getenv("CLICKHOUSE_CONNECT_TIMEOUT_SECONDS", "10")),
            send_receive_timeout_seconds=int(
                os.getenv("CLICKHOUSE_SEND_RECEIVE_TIMEOUT_SECONDS", "30")
            ),
        )


@lru_cache(maxsize=1)
def get_clickhouse_client(settings: ClickHouseSettings | None = None) -> Client:
    """The process-wide client. Callers share it under the repository lock."""
    return create_clickhouse_client(settings)


def create_clickhouse_client(settings: ClickHouseSettings | None = None) -> Client:
    """A client of one's own, for a caller that must not queue behind others.

    The shared client is serialised by a lock, so a long-lived reader (the SSE
    timeline poll) and the writers recording events contend for it: the reader
    can go a whole run without a turn, and the run's trace then arrives in one
    lump at the end instead of as it happens.
    """
    resolved = settings or ClickHouseSettings.from_env()

    # ClickHouse Cloud suspends when idle, and the first connection after that
    # is refused rather than queued behind the resume. Wait it out: a visitor
    # opening the first drill-down of the day should get a pause, not an error.
    delays = list(wake_delays())
    for attempt, delay in enumerate((*delays, None)):
        try:
            return clickhouse_connect.get_client(
                host=resolved.host,
                port=resolved.port,
                username=resolved.username,
                password=resolved.password,
                database=resolved.database,
                secure=resolved.secure,
                connect_timeout=resolved.connect_timeout_seconds,
                send_receive_timeout=resolved.send_receive_timeout_seconds,
            )
        except Exception as error:
            if delay is None or not is_wake_error(error):
                raise
            logger.info(
                "ClickHouse looks suspended (%s); retrying in %.1fs (%d of %d)",
                type(error).__name__,
                delay,
                attempt + 1,
                len(delays),
            )
            time.sleep(delay)
    raise AssertionError("unreachable: the final attempt either returns or raises")
