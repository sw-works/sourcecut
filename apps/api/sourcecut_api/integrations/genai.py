"""One place that decides how SourceCut reaches Gemini.

Two backends answer the same API. **Vertex AI** authenticates with the
environment's Google credentials and bills to a project, which is what the
deployed services use. The **Gemini API** authenticates with a key, which is
what a laptop or a CI job usually has.

Every call site used to make that choice for itself, and they disagreed: the
planner pinned ``vertexai=False``, the embedder passed a key when it had one and
otherwise let the library guess, and a service configured for Vertex with no key
quietly degraded to the deterministic planner instead of saying why. The choice
is made once, here, and the same client shape comes back either way.

Vertex is selected by ``GOOGLE_GENAI_USE_VERTEXAI=true`` with
``GOOGLE_CLOUD_PROJECT`` and ``GOOGLE_CLOUD_LOCATION``; anything else falls back
to a key from ``GEMINI_API_KEY`` or ``GOOGLE_API_KEY``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

DEFAULT_LOCATION = "us-central1"
#: Values that look like a filled-in template rather than a credential.
PLACEHOLDER_MARKERS = ("replace", "your-", "changeme", "example", "placeholder")


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of true/false, 1/0, yes/no, or on/off")


@dataclass(frozen=True, slots=True)
class GenaiSettings:
    """How to reach Gemini, resolved from the environment."""

    #: "vertex", "api_key", or "none" when neither is configured.
    backend: str
    project: str = ""
    location: str = DEFAULT_LOCATION
    api_key: str = ""

    @property
    def configured(self) -> bool:
        return self.backend != "none"

    @property
    def description(self) -> str:
        if self.backend == "vertex":
            return f"Vertex AI · {self.project} · {self.location}"
        if self.backend == "api_key":
            return "Gemini API key"
        return "no Gemini credential"

    @classmethod
    def from_env(cls, *, api_key: str | None = None) -> GenaiSettings:
        """Resolve the backend. An explicit api_key wins, for callers that hold one."""
        if api_key and not _is_placeholder(api_key):
            return cls(backend="api_key", api_key=api_key)
        if _env_flag("GOOGLE_GENAI_USE_VERTEXAI"):
            project = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
            if not project or _is_placeholder(project):
                raise ValueError(
                    "GOOGLE_GENAI_USE_VERTEXAI is set, so GOOGLE_CLOUD_PROJECT must name "
                    "a real project"
                )
            location = (os.getenv("GOOGLE_CLOUD_LOCATION") or DEFAULT_LOCATION).strip()
            return cls(backend="vertex", project=project, location=location or DEFAULT_LOCATION)
        resolved = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        if resolved and not _is_placeholder(resolved):
            return cls(backend="api_key", api_key=resolved)
        return cls(backend="none")


def create_genai_client(
    settings: GenaiSettings | None = None,
    *,
    api_key: str | None = None,
) -> Any:
    """Build a google-genai client for whichever backend is configured."""
    from google import genai

    resolved = settings or GenaiSettings.from_env(api_key=api_key)
    if resolved.backend == "vertex":
        return genai.Client(
            vertexai=True, project=resolved.project, location=resolved.location
        )
    if resolved.backend == "api_key":
        # vertexai=False is explicit: an inherited GOOGLE_GENAI_USE_VERTEXAI would
        # otherwise make the client ignore the key and fail on Vertex auth.
        return genai.Client(api_key=resolved.api_key, vertexai=False)
    raise ValueError(
        "No Gemini credential: set GOOGLE_GENAI_USE_VERTEXAI=true with "
        "GOOGLE_CLOUD_PROJECT, or GEMINI_API_KEY"
    )
