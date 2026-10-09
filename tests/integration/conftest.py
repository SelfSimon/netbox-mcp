"""Common setup for integration tests: they require a real NetBox instance.

These tests skip (rather than fail) as long as NETBOX_URL/NETBOX_TEST_TOKEN
aren't set, which allows committing them without breaking an unconfigured
local `pytest -m integration` run.

NETBOX_TEST_TOKEN is a personal NetBox API token on the test instance (with
netbox_branching view/add permissions). The server has no service-account
fallback (NETBOX-115), so this fixture plays the role the HTTP middleware
plays in production: it puts the token in the per-request contextvar for
the tools, and into `get_settings()` for tests that build a
`NetBoxRestClient()` directly.
"""

import os
from dataclasses import replace

import pytest

import client.rest
from client.config import get_settings
from netbox_mcp.auth import _current_token


def _missing_env_vars() -> list[str]:
    required = ("NETBOX_URL", "NETBOX_TEST_TOKEN")
    return [name for name in required if not os.environ.get(name)]


# Module scope (not session): set before the module-scoped fixtures that
# create branches, and reset before the unit tests run in the same session.
@pytest.fixture(scope="module", autouse=True)
def _require_real_netbox_instance():
    missing = _missing_env_vars()
    if missing:
        pytest.skip(
            "Integration tests disabled: missing variable(s) "
            f"{', '.join(missing)} (requires a real NetBox instance "
            "with netbox_branching installed)."
        )

    token = os.environ["NETBOX_TEST_TOKEN"]
    reset = _current_token.set(token)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            client.rest,
            "get_settings",
            lambda: replace(get_settings(), netbox_api_token=token),
        )
        yield
    _current_token.reset(reset)
