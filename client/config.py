"""Data client configuration, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .exceptions import NetBoxConfigurationError


@dataclass(frozen=True)
class ClientSettings:
    netbox_url: str
    netbox_api_token: str = ""
    netbox_ui_url: str = ""
    timeout: float = 10.0
    max_retries: int = 2


def get_ui_url() -> str:
    """`NETBOX_UI_URL` without its trailing slash, or "" when unset.

    Needs no other variable, so a message can link the NetBox UI even where
    get_settings() would fail.
    """
    return os.environ.get("NETBOX_UI_URL", "").rstrip("/")


def get_settings() -> ClientSettings:
    """Read configuration from environment variables.

    Only `NETBOX_URL` is required. No token is read from the environment:
    `netbox_api_token` is left empty here and always filled with the caller's
    own NetBox token (`netbox_mcp.auth.get_current_token`) — there is no
    service-account fallback.

    `NETBOX_UI_URL` is optional: the NetBox address as users open it in a
    browser, used only to build links in messages. `NETBOX_URL` is the
    address the server reaches NetBox at, often internal (e.g.
    `http://netbox:8080` in Docker), so it is never used for links.

    Raises NetBoxConfigurationError if NETBOX_URL is missing.
    """
    netbox_url = os.environ.get("NETBOX_URL")
    if not netbox_url:
        raise NetBoxConfigurationError("Missing environment variable(s): NETBOX_URL")

    timeout = float(os.environ.get("NETBOX_CLIENT_TIMEOUT", "10.0"))
    max_retries = int(os.environ.get("NETBOX_CLIENT_MAX_RETRIES", "2"))

    return ClientSettings(
        netbox_url=netbox_url.rstrip("/"),
        netbox_ui_url=get_ui_url(),
        timeout=timeout,
        max_retries=max_retries,
    )
