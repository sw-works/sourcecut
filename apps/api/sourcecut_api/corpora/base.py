from __future__ import annotations

from typing import Protocol

from sourcecut_api.models.corpus import CorpusDetail, CorpusRecord


class CorpusAdapter(Protocol):
    corpus_id: str

    def summary(self) -> CorpusRecord: ...

    def detail(self) -> CorpusDetail: ...


class CorpusRegistry:
    def __init__(self, adapters: tuple[CorpusAdapter, ...]) -> None:
        self._adapters = {adapter.corpus_id: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("Corpus adapter IDs must be unique")

    def list(self) -> tuple[CorpusRecord, ...]:
        return tuple(
            adapter.summary()
            for adapter in sorted(self._adapters.values(), key=lambda item: item.corpus_id)
        )

    def get(self, corpus_id: str) -> CorpusDetail | None:
        adapter = self._adapters.get(corpus_id)
        return adapter.detail() if adapter is not None else None
