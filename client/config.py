"""Data client configuration, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .exceptions import NetBoxConfigurationError


@dataclass(frozen=True)
class ClientSettings:
    netbox_url: str
    netbox_api_token: str
    timeout: float = 10.0
    max_retries: int = 2


def get_settings() -> ClientSettings:
    """Read configuration from environment variables.

    `netbox_api_token` here is the dev/test/CI fallback (service account).
    In real MCP usage, each request builds its own `ClientSettings` from the
    caller's personal NetBox token instead of calling this function — see
    `netbox_mcp.auth`.

    Raises NetBoxConfigurationError if a required variable is missing.
    """
    netbox_url = os.environ.get("NETBOX_URL")
    netbox_api_token = os.environ.get("NETBOX_API_TOKEN")

    missing = [
        name
        for name, value in (
            ("NETBOX_URL", netbox_url),
            ("NETBOX_API_TOKEN", netbox_api_token),
        )
        if not value
    ]
    if missing:
        raise NetBoxConfigurationError(
            f"Missing environment variable(s): {', '.join(missing)}"
        )

    timeout = float(os.environ.get("NETBOX_CLIENT_TIMEOUT", "10.0"))
    max_retries = int(os.environ.get("NETBOX_CLIENT_MAX_RETRIES", "2"))

    return ClientSettings(
        netbox_url=netbox_url.rstrip("/"),
        netbox_api_token=netbox_api_token,
        timeout=timeout,
        max_retries=max_retries,
    )
