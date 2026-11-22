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

Every branch created during the session is deleted at its end
(NETBOX-148): writes only ever land in branches, so this leaves no test
data behind. The token therefore also needs
`netbox_branching.delete_branch` on the test instance. Deleting a branch
is a test-only cleanup; the MCP itself never exposes it.
"""

import os
import uuid
from dataclasses import replace

import pytest

import client.rest
from client.config import get_settings
from client.exceptions import NetBoxClientError
from client.rest import MAX_LIST_LIMIT, NetBoxRestClient
from netbox_mcp.auth import _current_token

_BRANCHES_PATH = "plugins/branching/branches/"


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


def _branch_ids(rest: NetBoxRestClient) -> set[int]:
    ids: set[int] = set()
    while True:
        page = rest._page(
            _BRANCHES_PATH,
            {"ordering": "id", "limit": MAX_LIST_LIMIT, "offset": len(ids)},
        )
        ids |= {b["id"] for b in page["results"]}
        if not page["results"] or len(ids) >= page["count"]:
            return ids


@pytest.fixture(scope="session", autouse=True)
def _delete_the_branches_this_session_created():
    """Delete, at the end of the session, every branch that did not exist
    at its start — so whoever else creates one on the test instance during
    the run loses it too: run against a dev instance only."""
    if _missing_env_vars():
        yield
        return
    settings = replace(get_settings(), netbox_api_token=os.environ["NETBOX_TEST_TOKEN"])
    with NetBoxRestClient(settings) as rest:
        before = _branch_ids(rest)
        yield
        left = []
        for branch_id in sorted(_branch_ids(rest) - before):
            try:
                rest._request("DELETE", f"{_BRANCHES_PATH}{branch_id}/")
            except NetBoxClientError as exc:
                left.append(f"{branch_id}: {exc}")
    if left:
        pytest.fail(
            "Test branches left on the instance, delete them in the NetBox UI:\n"
            + "\n".join(left)
        )


@pytest.fixture
def main_site():
    """Create sites directly on main, for the tests of reads (reads only see
    main), and delete them by id once the test is over (NETBOX-148).

    `NetBoxRestClient.delete()` refuses to run outside a branch; this
    test-only cleanup goes around it, for the objects the test created.
    """
    created: list[dict] = []

    def make(**extra) -> dict:
        slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
        with NetBoxRestClient() as rest:
            site = rest.create("site", {"name": slug, "slug": slug, **extra})
        created.append(site)
        return site

    yield make
    with NetBoxRestClient() as rest:
        for site in created:
            rest._request("DELETE", f"dcim/sites/{site['id']}/")
