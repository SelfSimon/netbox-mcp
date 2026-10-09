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


def test_get_current_token_uses_contextvar_when_set():
    reset = _current_token.set("per-request-token")
    try:
        assert get_current_token() == "per-request-token"
    finally:
        _current_token.reset(reset)


def test_get_current_token_has_no_env_var_fallback(monkeypatch):
    # NETBOX-115: a leftover service-account token must never be used.
    monkeypatch.setenv("NETBOX_API_TOKEN", "service-account-token")
    assert _current_token.get() is None

    with pytest.raises(NetBoxConfigurationError, match="Authorization"):
        get_current_token()


async def _whoami(request):
    return JSONResponse({"token": _current_token.get()})


def _make_app() -> Starlette:
    app = Starlette(routes=[Route("/whoami", _whoami)])
    app.add_middleware(TokenCaptureMiddleware)
    return app


def test_middleware_captures_token_for_the_request():
    client = TestClient(_make_app())

    response = client.get("/whoami", headers={"Authorization": "Bearer user-token"})

    assert response.json() == {"token": "user-token"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc123"}])
def test_middleware_rejects_request_without_token(headers):
    client = TestClient(_make_app())

    response = client.get("/whoami", headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer")
    assert "Authorization" in response.json()["error"]


def test_middleware_resets_contextvar_between_requests():
    client = TestClient(_make_app())

    first = client.get("/whoami", headers={"Authorization": "Bearer user-token"})
    second = client.get("/whoami", headers={"Authorization": "Token other-token"})

    assert first.json() == {"token": "user-token"}
    assert second.json() == {"token": "other-token"}
    assert _current_token.get() is None
