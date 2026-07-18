import pytest

from client.config import get_settings
from client.exceptions import NetBoxConfigurationError


def test_get_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local/")
    monkeypatch.setenv("NETBOX_API_TOKEN", "abc123")
    monkeypatch.delenv("NETBOX_CLIENT_TIMEOUT", raising=False)
    monkeypatch.delenv("NETBOX_CLIENT_MAX_RETRIES", raising=False)

    settings = get_settings()

    assert settings.netbox_url == "http://netbox.local"  # trailing slash stripped
    assert settings.netbox_api_token == "abc123"
    assert settings.timeout == 10.0
    assert settings.max_retries == 2


def test_get_settings_reads_optional_overrides(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local")
    monkeypatch.setenv("NETBOX_API_TOKEN", "abc123")
    monkeypatch.setenv("NETBOX_CLIENT_TIMEOUT", "5")
    monkeypatch.setenv("NETBOX_CLIENT_MAX_RETRIES", "0")

    settings = get_settings()

    assert settings.timeout == 5.0
    assert settings.max_retries == 0


@pytest.mark.parametrize("missing_var", ["NETBOX_URL", "NETBOX_API_TOKEN"])
def test_get_settings_raises_on_missing_variable(monkeypatch, missing_var):
    values = {
        "NETBOX_URL": "http://netbox.local",
        "NETBOX_API_TOKEN": "abc123",
    }
    for name, value in values.items():
        if name == missing_var:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    with pytest.raises(NetBoxConfigurationError):
        get_settings()
