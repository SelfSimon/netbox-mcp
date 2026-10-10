"""Integration tests for the REST client, against a real NetBox instance.

Requires NETBOX_URL pointing to a running NetBox instance with
netbox_branching installed, and NETBOX_TEST_TOKEN holding a personal API
token on it with netbox_branching view/add permissions (see conftest.py).

Merging is not tested here: the token may well hold merge_branch (an admin's
does), so the guard against merging into `main` is the absence of any
merge/sync/revert call in the client — covered by
tests/unit/test_branches.py, not by a NetBox permission.

Test objects created here (sites, branches) accumulate in the target
instance; clean them up periodically by hand in the NetBox UI. Names/slugs
are suffixed with a random id to avoid collisions between runs.
"""

import uuid

import pytest

from client.branches import create_branch, wait_until_ready
from client.exceptions import NetBoxNoBranchError, NetBoxValidationError
from client.rest import NetBoxRestClient

pytestmark = pytest.mark.integration


def test_create_and_patch_site_round_trip():
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"

    with NetBoxRestClient() as rest_client:
        created = rest_client.create("site", {"name": slug, "slug": slug})
        assert created["name"] == slug

        patched = rest_client.patch(
            "site",
            created["id"],
            {"description": "created by netbox-mcp integration tests"},
        )
        assert patched["description"] == "created by netbox-mcp integration tests"


def test_create_rejects_invalid_payload():
    with NetBoxRestClient() as rest_client, pytest.raises(NetBoxValidationError):
        rest_client.create("site", {})


def test_delete_outside_a_branch_is_refused_client_side():
    with NetBoxRestClient() as rest_client, pytest.raises(NetBoxNoBranchError):
        rest_client.delete("site", 1)


def test_branch_write_is_invisible_on_main_and_visible_with_branch_header():
    branch_name = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"

    with NetBoxRestClient() as bootstrap_client:
        branch = create_branch(bootstrap_client, branch_name)
        branch = wait_until_ready(bootstrap_client, branch["id"])

    with NetBoxRestClient(branch=branch["schema_id"]) as branch_client:
        created = branch_client.create("site", {"name": slug, "slug": slug})

    with NetBoxRestClient() as main_client:
        # not visible on main without the branch header
        assert main_client.list("site", filters={"slug": slug}) == []

    with NetBoxRestClient(branch=branch["schema_id"]) as branch_client:
        found = branch_client.get("site", created["id"])
        assert found["slug"] == slug


def test_delete_inside_a_branch_succeeds():
    branch_name = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"

    with NetBoxRestClient() as bootstrap_client:
        branch = create_branch(bootstrap_client, branch_name)
        branch = wait_until_ready(bootstrap_client, branch["id"])

    with NetBoxRestClient(branch=branch["schema_id"]) as branch_client:
        created = branch_client.create("site", {"name": slug, "slug": slug})
        branch_client.delete("site", created["id"])

    with NetBoxRestClient(branch=branch["schema_id"]) as branch_client:
        assert branch_client.list("site", filters={"slug": slug}) == []
