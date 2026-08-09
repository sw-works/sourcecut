from __future__ import annotations

import pytest

from sourcecut_api.telemetry import configure_telemetry, sanitize_sql


def test_sql_telemetry_redacts_literals_and_normalizes_whitespace() -> None:
    query = """
SELECT passage_id
FROM sourcecut.passages
WHERE entry_date BETWEEN 18050909 AND 18050930
  AND positionCaseInsensitiveUTF8(passage_text, 'snow') > 0
LIMIT 20;
"""

    sanitized = sanitize_sql(query)

    assert "snow" not in sanitized
    assert "18050909" not in sanitized
    assert "BETWEEN ? AND ?" in sanitized
    assert sanitized.endswith("LIMIT ?")
    assert "\n" not in sanitized


def test_telemetry_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCECUT_TELEMETRY_ENABLED", raising=False)
    assert configure_telemetry() is False


def test_enabled_telemetry_requires_real_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCECUT_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "https://replace-with-grafana-otlp-endpoint",
    )

    with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
        configure_telemetry()


def test_enabled_telemetry_requires_authenticated_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCECUT_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example.com")
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_HEADERS",
        "Authorization=Basic%20replace-with-grafana-otlp-token",
    )

    with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_HEADERS"):
        configure_telemetry()
