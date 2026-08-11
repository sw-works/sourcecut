from __future__ import annotations

from typing import Protocol

from sourcecut_api.models import JournalEntry


class JournalParser(Protocol):
    def __call__(self, source_text: str) -> tuple[JournalEntry, ...]: ...
