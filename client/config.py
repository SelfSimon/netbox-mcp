"""Data client configuration, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .exceptions import NetBoxConfigurationError


@dataclass(frozen=True)
class ClientSettings:
    netbox_url: str
    netbox_api_token: str = ""
    timeout: float = 10.0
    max_retries: int = 2


def get_settings() -> ClientSettings:
    """Read configuration from environment variables.

    Only `NETBOX_URL` is required. `netbox_api_token` here is the dev/test/CI
    fallback (service account) and defaults to "" when unset — real MCP
    requests always overwrite it with the caller's personal NetBox token via
    `netbox_mcp.auth.get_current_token`, which raises its own clear error if
    neither a per-request token nor this fallback is available. Requiring
    `NETBOX_API_TOKEN` here as well would raise before that per-request token
    is ever considered.

    Raises NetBoxConfigurationError if NETBOX_URL is missing.
    """
    netbox_url = os.environ.get("NETBOX_URL")
    if not netbox_url:
        raise NetBoxConfigurationError("Missing environment variable(s): NETBOX_URL")

    netbox_api_token = os.environ.get("NETBOX_API_TOKEN", "")
    timeout = float(os.environ.get("NETBOX_CLIENT_TIMEOUT", "10.0"))
    max_retries = int(os.environ.get("NETBOX_CLIENT_MAX_RETRIES", "2"))

    return ClientSettings(
        netbox_url=netbox_url.rstrip("/"),
        netbox_api_token=netbox_api_token,
        timeout=timeout,
        max_retries=max_retries,
    )
