"""Recognising a ClickHouse Cloud service that is waking up.

A ClickHouse Cloud service suspends after a period of inactivity, and the first
connection after that does not queue behind the resume — it fails. The service
then comes back within a few seconds, so the failure is a pause wearing the
costume of an error, and the only caller who should ever see it is one that has
already waited through the resume and been refused again.

This module names that failure and nothing else. A refused query, a syntax
error, a permission denial and a row-limit breach are all real answers that
another attempt would only repeat more slowly, so the predicate is deliberately
narrow: it matches the shapes a suspended or resuming service produces, and
anything it does not recognise is raised at once.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

DEFAULT_WAKE_RETRIES = 3
DEFAULT_WAKE_BACKOFF_SECONDS = 1.5

# What a suspended, resuming or unreachable ClickHouse Cloud endpoint says, in
# the words its own driver and gateway use. Matched case-insensitively against
# the whole exception text, so a wrapped cause still counts.
WAKE_SIGNATURES: tuple[str, ...] = (
    "service is not running",
    "service is starting",
    "is currently starting",
    "is resuming",
    "waking",
    "service unavailable",
    "temporarily unavailable",
    "bad gateway",
    "gateway timeout",
    "connection refused",
    "connection reset",
    "connection aborted",
    "connection error",
    "server disconnected",
    "remote end closed connection",
    "timed out",
    "timeout",
    "name or service not known",
    "temporary failure in name resolution",
    "502",
    "503",
    "504",
)


def is_wake_error(error: BaseException | str) -> bool:
    """True when another attempt is worth making, false for a real answer."""
    text = str(error).lower()
    if not text:
        return False
    return any(signature in text for signature in WAKE_SIGNATURES)


def wake_retries() -> int:
    """How many extra attempts a wake is worth. Zero disables the retry."""
    raw = os.getenv("CLICKHOUSE_WAKE_RETRIES")
    if raw is None or not raw.strip():
        return DEFAULT_WAKE_RETRIES
    value = int(raw)
    if value < 0:
        raise ValueError("CLICKHOUSE_WAKE_RETRIES cannot be negative")
    return value


def wake_backoff_seconds() -> float:
    """The first pause between attempts; each later one doubles it."""
    raw = os.getenv("CLICKHOUSE_WAKE_BACKOFF_SECONDS")
    if raw is None or not raw.strip():
        return DEFAULT_WAKE_BACKOFF_SECONDS
    value = float(raw)
    if value <= 0:
        raise ValueError("CLICKHOUSE_WAKE_BACKOFF_SECONDS must be positive")
    return value


def wake_delays(retries: int | None = None, backoff: float | None = None) -> Iterator[float]:
    """The pauses to take between attempts, longest last."""
    attempts = wake_retries() if retries is None else retries
    first = wake_backoff_seconds() if backoff is None else backoff
    for index in range(attempts):
        yield first * (2**index)
