"""Integration tests for tools/write.py, against a real NetBox instance.

Requires NETBOX_URL / NETBOX_API_TOKEN pointing to a running NetBox instance
with the svc-netbox-mcp service account provisioned (see
scripts/create_service_account.py) — same prerequisites as
test_rest_integration.py.

Every write tool call here happens inside a netbox_branching branch created
for the test; nothing reaches `main` directly (merge stays a human action
from the NetBox UI, see client/branches.py).

Test objects (branches, and everything created inside them) accumulate in
the target instance; clean them up periodically by hand, same as
test_rest_integration.py.
"""

import uuid

import pytest

from client.exceptions import NetBoxNotFoundError
from client.rest import NetBoxRestClient
from schemas.writes import (
    DeviceCreate,
    DeviceUpdate,
    InterfaceCreate,
    InterfaceUpdate,
    IPAddressAssign,
)
from tools import write

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def branch() -> str:
    """A single ready netbox_branching branch shared by this module's tests.

    Branch provisioning takes ~20s; every test here uses uuid-suffixed
    names, so sharing one branch across the module is safe and keeps the
    suite from re-paying that cost per test.
    """
    name = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    created = write.create_branch(name, "netbox-mcp write-tools integration test")
    return created["schema_id"]


@pytest.fixture(scope="module")
def device_prereqs(branch: str) -> dict[str, int]:
    """Manufacturer/device type/role/site created inside `branch`, so the
    device/interface write tools under test have somewhere to attach to.
    """
    suffix = uuid.uuid4().hex[:8]
    with NetBoxRestClient(branch=branch) as client:
        manufacturer = client.create(
            "manufacturer",
            {"name": f"mcp-test-{suffix}", "slug": f"mcp-test-{suffix}"},
        )
        device_type = client.create(
            "device_type",
            {
                "manufacturer": manufacturer["id"],
                "model": f"mcp-test-{suffix}",
                "slug": f"mcp-test-{suffix}",
            },
        )
        role = client.create(
            "device_role",
            {"name": f"mcp-test-{suffix}", "slug": f"mcp-test-{suffix}"},
        )
        site = client.create(
            "site", {"name": f"mcp-test-{suffix}", "slug": f"mcp-test-{suffix}"}
        )
    return {
        "device_type": device_type["id"],
        "role": role["id"],
        "site": site["id"],
    }


def _device_payload(prereqs: dict[str, int], name: str) -> DeviceCreate:
    return DeviceCreate(
        name=name,
        device_type=prereqs["device_type"],
        role=prereqs["role"],
        site=prereqs["site"],
    )


def test_create_branch_returns_a_ready_branch_with_schema_id():
    name = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    result = write.create_branch(name)
    assert result["status"]["value"] == "ready"
    assert result["schema_id"]


def test_list_branches_includes_a_freshly_created_branch(branch):
    schema_ids = {b["schema_id"] for b in write.list_branches()}
    assert branch in schema_ids


def test_create_device_and_update_it_inside_a_branch(branch, device_prereqs):
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    created = write.create_device(_device_payload(device_prereqs, slug), branch=branch)
    assert created["name"] == slug

    updated = write.update_device(
        created["id"],
        DeviceUpdate(comments="updated by netbox-mcp integration tests"),
        branch=branch,
    )
    assert updated["comments"] == "updated by netbox-mcp integration tests"


def test_device_created_in_a_branch_is_not_visible_on_main(branch, device_prereqs):
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    write.create_device(_device_payload(device_prereqs, slug), branch=branch)

    with NetBoxRestClient() as main_client:
        assert main_client.list("device", {"name": slug}) == []


def test_update_device_missing_raises_not_found(branch):
    with pytest.raises(NetBoxNotFoundError):
        write.update_device(999_999_999, DeviceUpdate(comments="x"), branch=branch)


def test_create_interface_and_update_it_inside_a_branch(branch, device_prereqs):
    device = write.create_device(
        _device_payload(device_prereqs, f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"),
        branch=branch,
    )

    created = write.create_interface(
        InterfaceCreate(device=device["id"], name="eth0", type="1000base-t"),
        branch=branch,
    )
    assert created["name"] == "eth0"

    updated = write.update_interface(
        created["id"], InterfaceUpdate(enabled=False), branch=branch
    )
    assert updated["enabled"] is False


def test_update_interface_missing_raises_not_found(branch):
    with pytest.raises(NetBoxNotFoundError):
        write.update_interface(
            999_999_999, InterfaceUpdate(enabled=False), branch=branch
        )


def test_assign_ip_address_to_an_interface_inside_a_branch(branch, device_prereqs):
    device = write.create_device(
        _device_payload(device_prereqs, f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"),
        branch=branch,
    )
    interface = write.create_interface(
        InterfaceCreate(device=device["id"], name="eth0", type="1000base-t"),
        branch=branch,
    )

    octet = uuid.uuid4().int % 250 + 1
    address = f"10.99.{octet}.1/32"
    created = write.assign_ip_address(
        IPAddressAssign(address=address, assigned_object_id=interface["id"]),
        branch=branch,
    )
    assert created["address"] == address
    assert created["assigned_object_id"] == interface["id"]
