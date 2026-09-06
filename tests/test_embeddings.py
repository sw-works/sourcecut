from __future__ import annotations

import hashlib
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest

from pipelines.embeddings.gemini import EmbeddingSettings, GeminiEmbedder
from sourcecut_api.db.embed import EmbeddingBackfillService


class DeterministicEmbedder:
    def __init__(self, model: str = "fake-embedding") -> None:
        self.settings = SimpleNamespace(model=model)
        self.calls: list[tuple[str, ...]] = []

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.calls.append(tuple(texts))
        return tuple(_hash_vector(text) for text in texts)

    def embed_query(self, text: str) -> tuple[float, ...]:
        self.calls.append((text,))
        return _hash_vector(text)


def _hash_vector(text: str) -> tuple[float, ...]:
    digest = hashlib.sha256(text.encode()).digest()
    return tuple(byte / 255 for byte in digest[:4])


class FakeBackfillClient:
    def __init__(self) -> None:
        self.tables = {
            "passages": [
                {
                    "passage_id": "passage-1",
                    "passage_text": "The party was exhausted and starving.",
                    "embedding": [],
                    "embedding_model": "",
                }
            ],
            "media_assets": [
                {
                    "asset_id": "asset-1",
                    "title": "Mountain trail",
                    "description": "A steep route",
                    "subjects": ["Lewis and Clark"],
                    "raw_metadata": "{}",
                    "embedding": [],
                    "embedding_model": "",
                }
            ],
        }

    def query(self, query: str, parameters: dict[str, object]) -> SimpleNamespace:
        table = "passages" if "FROM passages FINAL" in query else "media_assets"
        rows = [
            row
            for row in self.tables[table]
            if row["embedding_model"] != parameters["model"]
        ][: int(parameters["limit"])]
        columns = list(self.tables[table][0])
        return SimpleNamespace(
            column_names=columns,
            result_rows=[tuple(row[column] for column in columns) for row in rows],
        )

    def insert(
        self,
        table: str,
        rows: list[list[object]],
        *,
        column_names: list[str],
        settings: dict[str, int],
    ) -> None:
        del settings
        id_field = "passage_id" if table == "passages" else "asset_id"
        for values in rows:
            replacement = dict(zip(column_names, values, strict=True))
            target = next(
                row for row in self.tables[table] if row[id_field] == replacement[id_field]
            )
            target.update(replacement)


def test_backfill_is_resumable_noop_and_model_swap_reembeds() -> None:
    client = FakeBackfillClient()
    first_embedder = DeterministicEmbedder()
    service = EmbeddingBackfillService(client, first_embedder, batch_size=1)

    first = service.run()
    second = service.run()
    swapped = EmbeddingBackfillService(
        client, DeterministicEmbedder("fake-embedding-v2"), batch_size=1
    ).run()

    assert (first.passages_embedded, first.media_assets_embedded) == (1, 1)
    assert (second.passages_embedded, second.media_assets_embedded) == (0, 0)
    assert (swapped.passages_embedded, swapped.media_assets_embedded) == (1, 1)


def test_embedding_guard_blocks_disabled_and_placeholder_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "replace-with-gemini-api-key")

    with pytest.raises(ValueError, match="ENABLED"):
        EmbeddingSettings(enabled=False).validate()
    with pytest.raises(ValueError, match="Gemini credential"):
        EmbeddingSettings(enabled=True).validate()


def test_embedding_guard_accepts_a_vertex_project_with_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vertex is a credential too: the deployed services carry no API key."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "sourcecut-test")

    EmbeddingSettings(enabled=True).validate()


def test_gemini_embedder_batches_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class Models:
        def __init__(self) -> None:
            self.calls = 0
            self.last_contents: list[Any] = []

        def embed_content(self, **kwargs: Any) -> Any:
            self.calls += 1
            self.last_contents = kwargs["contents"]
            if self.calls == 1:
                raise TimeoutError("retry")
            return SimpleNamespace(
                embeddings=[
                    SimpleNamespace(values=[0.1] * 128) for _ in kwargs["contents"]
                ]
            )

    models = Models()
    embedder = GeminiEmbedder(
        SimpleNamespace(models=models),
        EmbeddingSettings(enabled=True, dimension=128, attempts=2),
        sleep=lambda _: None,
    )

    vectors = embedder.embed_documents(("one", "two"))
    assert len(vectors) == 2
    assert all(len(vector) == 128 for vector in vectors)
    assert models.calls == 2
    assert [content.parts[0].text for content in models.last_contents] == ["one", "two"]
