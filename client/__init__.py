"""NetBox data client — 100% REST API, branch-first writes.

`rest.NetBoxRestClient` handles both read and write; `branches` provides the
branch lifecycle helpers a write flow needs (create, wait for readiness) —
deliberately not merge/sync/revert/archive, which are human-only actions.
"""

from . import branches, exceptions, rest
from .config import ClientSettings, get_settings
from .exceptions import NetBoxClientError
from .rest import NetBoxRestClient

__all__ = [
    "ClientSettings",
    "NetBoxClientError",
    "NetBoxRestClient",
    "branches",
    "exceptions",
    "get_settings",
    "rest",
]
