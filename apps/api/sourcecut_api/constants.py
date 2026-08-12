"""Shared research-window constants.

The demo corpus slice is the Bitterroot crossing. Every module that scopes a
query to the window imports these instead of repeating the literals.
"""

from __future__ import annotations

from datetime import date, timedelta

BITTERROOT_START = 18050909
BITTERROOT_END = 18050930


def window_dates(start: int = BITTERROOT_START, end: int = BITTERROOT_END) -> tuple[int, ...]:
    """Calendar dates in the window as YYYYMMDD ints.

    Iterates real dates, so windows that cross a month boundary never yield
    impossible values like 18050931.
    """
    first = date(start // 10000, start // 100 % 100, start % 100)
    last = date(end // 10000, end // 100 % 100, end % 100)
    days: list[int] = []
    current = first
    while current <= last:
        days.append(current.year * 10000 + current.month * 100 + current.day)
        current += timedelta(days=1)
    return tuple(days)
