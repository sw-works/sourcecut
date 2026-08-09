from unittest.mock import Mock, patch

import pytest

from sourcecut_api.db.client import ClickHouseSettings, get_clickhouse_client


def test_settings_use_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CLICKHOUSE_HOST",
        "CLICKHOUSE_PORT",
        "CLICKHOUSE_USERNAME",
        "CLICKHOUSE_PASSWORD",
        "CLICKHOUSE_DATABASE",
        "CLICKHOUSE_SECURE",
    ):
        monkeypatch.delenv(name, raising=False)

    assert ClickHouseSettings.from_env() == ClickHouseSettings()


def test_secure_settings_default_to_cloud_https_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLICKHOUSE_SECURE", "true")
    monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)

    settings = ClickHouseSettings.from_env()

    assert settings.secure is True
    assert settings.port == 8443


def test_client_factory_reuses_the_long_lived_client() -> None:
    settings = ClickHouseSettings(password="secret")
    expected_client = Mock()
    get_clickhouse_client.cache_clear()

    with patch("sourcecut_api.db.client.clickhouse_connect.get_client") as factory:
        factory.return_value = expected_client
        first = get_clickhouse_client(settings)
        second = get_clickhouse_client(settings)

    assert first is expected_client
    assert second is expected_client
    factory.assert_called_once_with(
        host="localhost",
        port=8123,
        username="default",
        password="secret",
        database="default",
        secure=False,
        connect_timeout=10,
        send_receive_timeout=30,
    )
    get_clickhouse_client.cache_clear()
