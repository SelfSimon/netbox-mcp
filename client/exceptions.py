"""Exceptions shared by the NetBox data client.

The client exclusively raises subclasses of NetBoxClientError, never a raw
httpx exception — this lets `tools/` catch just one family of errors.

Prefixed "NetBox" so as not to shadow the Python builtin exceptions of the
same name (PermissionError, ConnectionError): both families can be imported
side by side without ambiguity.
"""


class NetBoxClientError(Exception):
    """Base error for the NetBox data client."""


class NetBoxConfigurationError(NetBoxClientError):
    """Missing or invalid configuration (environment variables, etc.)."""


class NetBoxNotFoundError(NetBoxClientError):
    """The requested object does not exist."""


class NetBoxValidationError(NetBoxClientError):
    """The submitted data was rejected by NetBox (400)."""

    def __init__(self, message: str, errors: dict | None = None) -> None:
        super().__init__(message)
        self.errors = errors or {}


class NetBoxPermissionError(NetBoxClientError):
    """The service account lacks the required permissions (401/403)."""


class NetBoxConnectionError(NetBoxClientError):
    """Failed to communicate with NetBox (network, timeout, 429, 5xx)."""


class NetBoxNoBranchError(NetBoxClientError):
    """A destructive operation (delete) was attempted without an active
    `netbox_branching` branch.

    Defense in depth: writes must go through a branch so nothing reaches
    `main` without a human merge approval. Raised client-side, before the
    request even reaches NetBox.
    """
