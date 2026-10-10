import pytest

from client.config import get_settings
from client.exceptions import NetBoxConfigurationError


def test_get_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local/")
    monkeypatch.delenv("NETBOX_CLIENT_TIMEOUT", raising=False)
    monkeypatch.delenv("NETBOX_CLIENT_MAX_RETRIES", raising=False)

    settings = get_settings()

    assert settings.netbox_url == "http://netbox.local"  # trailing slash stripped
    assert settings.timeout == 10.0
    assert settings.max_retries == 2


def test_get_settings_reads_optional_overrides(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local")
    monkeypatch.setenv("NETBOX_CLIENT_TIMEOUT", "5")
    monkeypatch.setenv("NETBOX_CLIENT_MAX_RETRIES", "0")

    settings = get_settings()

    assert settings.timeout == 5.0
    assert settings.max_retries == 0


def test_get_settings_raises_on_missing_url(monkeypatch):
    monkeypatch.delenv("NETBOX_URL", raising=False)

    with pytest.raises(NetBoxConfigurationError):
        get_settings()


def test_get_settings_never_reads_a_token_from_the_environment(monkeypatch):
    # NETBOX-115: no service-account fallback — the token always comes from
    # the caller's request.
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local")
    monkeypatch.setenv("NETBOX_API_TOKEN", "service-account-token")

    settings = get_settings()

    assert settings.netbox_api_token == ""
