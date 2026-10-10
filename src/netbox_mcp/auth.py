"""Per-request NetBox token pass-through.

Each MCP call runs as the real NetBox user who made it — there is no shared
service account and no fallback token: the caller's own NetBox API token
travels as the request's `Authorization` header and is used as-is to build
that request's `NetBoxRestClient`. A request without one is refused with
`401` before it reaches any tool. NetBox itself is the only thing that ever
validates the token (on the first real REST call) — this module just makes
the raw bearer string available to tool handlers for the duration of the
request.

Deliberately not using `mcp.server.auth.settings.AuthSettings`: that flow is
built for full OAuth (mandatory `issuer_url`/`resource_server_url`,
discovery, dynamic client registration), which is more machinery than "the
user pastes their own NetBox token" needs. Instead, this mirrors the
contextvar-per-request pattern `netbox_branching` itself uses internally
(`netbox_branching/contextvars.py`): a Starlette middleware captures the
header into a `ContextVar` before the request reaches a tool handler, and
resets it afterwards.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_current_token: ContextVar[str | None] = ContextVar("_current_token", default=None)

MISSING_TOKEN_MESSAGE = (
    "No NetBox token for this request: send your own NetBox API token as "
    "'Authorization: Bearer <token>' (or 'Authorization: Token <token>')"
)


class TokenCaptureMiddleware:
    """Extracts the bearer/token string from `Authorization` into a contextvar.

    Accepts both `Authorization: Bearer <token>` and `Authorization: Token
    <token>` (NetBox's own scheme) so users can paste their NetBox token
    either way. Any HTTP request without a usable token gets `401` here,
    so no tool ever runs without the caller's own identity.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope)
        token = _extract_token(request.headers.get("authorization"))
        if token is None:
            response = JSONResponse(
                {"error": MISSING_TOKEN_MESSAGE},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="netbox-mcp"'},
            )
            await response(scope, receive, send)
            return

        reset_token: Token[str | None] = _current_token.set(token)
        try:
            await self._app(scope, receive, send)
        finally:
            _current_token.reset(reset_token)


def _extract_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    scheme, _, value = header_value.partition(" ")
    if scheme.lower() in ("bearer", "token") and value:
        return value
    return None


def get_current_token() -> str:
    """Return the NetBox token for the in-flight request.

    Raises NetBoxConfigurationError if no per-request token was captured —
    there is deliberately no service-account fallback.
    """
    from client.exceptions import NetBoxConfigurationError

    token = _current_token.get()
    if token:
        return token

    raise NetBoxConfigurationError(MISSING_TOKEN_MESSAGE)
