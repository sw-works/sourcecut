from __future__ import annotations

import pytest

from sourcecut_api.integrations.genai import GenaiSettings


def test_vertex_is_selected_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "sourcecut-64338")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-west1")

    settings = GenaiSettings.from_env()

    assert (settings.backend, settings.project, settings.location) == (
        "vertex",
        "sourcecut-64338",
        "us-west1",
    )
    assert settings.configured


def test_vertex_without_a_project_is_an_error_rather_than_a_silent_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Half-configured Vertex used to degrade the planner to static without saying why."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        GenaiSettings.from_env()


def test_vertex_beats_the_ambient_environment_but_not_an_explicit_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller holding a key means the Gemini API, whatever the environment says."""
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "sourcecut-64338")
    monkeypatch.setenv("GEMINI_API_KEY", "ambient-key")

    assert GenaiSettings.from_env().backend == "vertex"
    assert GenaiSettings.from_env(api_key="explicit-key").backend == "api_key"


def test_a_placeholder_key_is_not_a_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "replace-with-gemini-api-key")

    settings = GenaiSettings.from_env()

    assert settings.backend == "none"
    assert not settings.configured
    assert settings.description == "no Gemini credential"


def test_the_api_key_path_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-looking-key")

    settings = GenaiSettings.from_env()

    assert (settings.backend, settings.api_key) == ("api_key", "a-real-looking-key")
