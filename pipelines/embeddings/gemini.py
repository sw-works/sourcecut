from __future__ import annotations

import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from google.genai import types

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2"
PLACEHOLDER_MARKERS = ("replace-with", "placeholder", "your-")


class EmbeddingModelsClient(Protocol):
    def embed_content(self, **kwargs: Any) -> Any: ...


class EmbeddingClient(Protocol):
    models: EmbeddingModelsClient


@dataclass(frozen=True, slots=True)
class EmbeddingSettings:
    enabled: bool = False
    model: str = DEFAULT_EMBEDDING_MODEL
    dimension: int = 768
    attempts: int = 3

    @classmethod
    def from_env(cls) -> EmbeddingSettings:
        raw = os.getenv("SOURCECUT_EMBEDDING_ENABLED", "false").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            enabled = True
        elif raw in {"0", "false", "no", "off", ""}:
            enabled = False
        else:
            # Fail fast like every other SourceCut boolean env var instead of
            # silently treating a typo as disabled.
            raise ValueError(
                f"SOURCECUT_EMBEDDING_ENABLED has unsupported value {raw!r}"
            )
        return cls(
            enabled=enabled,
            model=os.getenv("SOURCECUT_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            dimension=int(os.getenv("SOURCECUT_EMBEDDING_DIMENSION", "768")),
        )

    def validate(self) -> None:
        if not self.enabled:
            raise ValueError("Set SOURCECUT_EMBEDDING_ENABLED=true to call Gemini embeddings")
        if not self.model or any(marker in self.model.lower() for marker in PLACEHOLDER_MARKERS):
            raise ValueError("SOURCECUT_EMBEDDING_MODEL must be a real model id")
        if not 128 <= self.dimension <= 3072:
            raise ValueError("SOURCECUT_EMBEDDING_DIMENSION must be between 128 and 3072")
        from sourcecut_api.integrations.genai import GenaiSettings

        if not GenaiSettings.from_env().configured:
            raise ValueError(
                "Embeddings need a Gemini credential: set GOOGLE_GENAI_USE_VERTEXAI=true "
                "with GOOGLE_CLOUD_PROJECT, or GEMINI_API_KEY"
            )


class GeminiEmbedder:
    def __init__(
        self,
        client: EmbeddingClient,
        settings: EmbeddingSettings,
        *,
        sleep: Any = time.sleep,
    ) -> None:
        self._client = client
        self.settings = settings
        self._sleep = sleep

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._embed((text,), "RETRIEVAL_QUERY")[0]

    def _embed(
        self, texts: Sequence[str], task_type: str
    ) -> tuple[tuple[float, ...], ...]:
        self.settings.validate()
        if not texts:
            return ()
        for attempt in range(1, self.settings.attempts + 1):
            try:
                response = self._client.models.embed_content(
                    model=self.settings.model,
                    contents=[
                        types.Content(parts=[types.Part(text=text)]) for text in texts
                    ],
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.settings.dimension,
                    ),
                )
            except ValueError:
                raise
            except Exception:
                if attempt == self.settings.attempts:
                    raise
                self._sleep(attempt)
                continue
            vectors = tuple(
                tuple(float(value) for value in embedding.values)
                for embedding in response.embeddings
            )
            # Shape mismatches are permanent contract violations, not transient
            # provider errors — never retried.
            if len(vectors) != len(texts):
                raise ValueError("Gemini returned the wrong number of embeddings")
            if any(len(vector) != self.settings.dimension for vector in vectors):
                raise ValueError("Gemini returned an unexpected embedding dimension")
            return vectors
        raise AssertionError("retry loop exhausted")


def create_embedder(
    settings: EmbeddingSettings | None = None,
    *,
    api_key: str | None = None,
) -> GeminiEmbedder:
    resolved = settings or EmbeddingSettings.from_env()
    resolved.validate()
    from sourcecut_api.integrations.genai import create_genai_client

    return GeminiEmbedder(create_genai_client(api_key=api_key), resolved)
