from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import clickhouse_connect

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
    resolved = settings or ClickHouseSettings.from_env()
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
