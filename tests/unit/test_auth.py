import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from client.exceptions import NetBoxConfigurationError
from netbox_mcp.auth import (
    TokenCaptureMiddleware,
    _current_token,
    _extract_token,
    get_current_token,
)


@pytest.mark.parametrize(
    "header_value,expected",
    [
        ("Bearer abc123", "abc123"),
        ("Token abc123", "abc123"),
        ("bearer abc123", "abc123"),
        (None, None),
        ("Basic abc123", None),
        ("Bearer", None),
    ],
)
def test_extract_token(header_value, expected):
    assert _extract_token(header_value) == expected


def test_get_current_token_uses_contextvar_when_set(monkeypatch):
    monkeypatch.delenv("NETBOX_API_TOKEN", raising=False)
    reset = _current_token.set("per-request-token")
    try:
        assert get_current_token() == "per-request-token"
    finally:
        _current_token.reset(reset)


def test_get_current_token_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("NETBOX_API_TOKEN", "service-account-token")
    assert _current_token.get() is None

    assert get_current_token() == "service-account-token"


def test_get_current_token_raises_when_nothing_available(monkeypatch):
    monkeypatch.delenv("NETBOX_API_TOKEN", raising=False)
    assert _current_token.get() is None

    with pytest.raises(NetBoxConfigurationError):
        get_current_token()


async def _whoami(request):
    return JSONResponse({"token": _current_token.get()})


def _make_app() -> Starlette:
    app = Starlette(routes=[Route("/whoami", _whoami)])
    app.add_middleware(TokenCaptureMiddleware)
    return app


def test_middleware_captures_token_for_the_request(monkeypatch):
    monkeypatch.delenv("NETBOX_API_TOKEN", raising=False)
    client = TestClient(_make_app())

    response = client.get("/whoami", headers={"Authorization": "Bearer user-token"})

    assert response.json() == {"token": "user-token"}


def test_middleware_leaves_contextvar_unset_without_header(monkeypatch):
    monkeypatch.delenv("NETBOX_API_TOKEN", raising=False)
    client = TestClient(_make_app())

    response = client.get("/whoami")

    assert response.json() == {"token": None}


def test_middleware_resets_contextvar_between_requests(monkeypatch):
    monkeypatch.delenv("NETBOX_API_TOKEN", raising=False)
    client = TestClient(_make_app())

    client.get("/whoami", headers={"Authorization": "Bearer user-token"})
    response = client.get("/whoami")

    assert response.json() == {"token": None}
    assert _current_token.get() is None
