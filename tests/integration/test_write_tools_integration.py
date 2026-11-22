"""Integration tests for tools/write.py, against a real NetBox instance.

Requires NETBOX_URL / NETBOX_TEST_TOKEN (see conftest.py) — same
prerequisites as test_rest_integration.py.

Every write tool call here happens inside a netbox_branching branch created
for the test; nothing reaches `main` directly (merge stays a human action
from the NetBox UI, see client/branches.py).

Test objects (branches, and everything created inside them) accumulate in
the target instance; clean them up periodically by hand, same as
test_rest_integration.py.
"""

import uuid

import pytest

from client.exceptions import NetBoxNotFoundError, NetBoxValidationError
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
    # Test branches accumulate in the target instance: take the largest page.
    page = write.list_branches(limit=1000)
    assert branch in {b["schema_id"] for b in page["results"]}


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


def test_get_branch_diff_shows_a_device_created_then_updated_in_the_branch(
    branch, device_prereqs
):
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    created = write.create_device(_device_payload(device_prereqs, slug), branch=branch)
    write.update_device(
        created["id"],
        DeviceUpdate(comments="checked by get_branch_diff"),
        branch=branch,
    )

    diff = write.get_branch_diff(branch, object_type="dcim.device", limit=1000)

    # One ChangeDiff per object: the create and the update are folded into
    # a single create holding the object's latest state.
    entries = [e for e in diff["results"] if e["object_id"] == created["id"]]
    assert len(entries) == 1
    assert entries[0]["action"] == "create"
    assert entries[0]["data"]["name"] == slug
    assert entries[0]["data"]["comments"] == "checked by get_branch_diff"
    assert diff["summary"]["create"] >= 1


def test_get_branch_diff_shows_the_fields_an_update_changes(branch):
    # An object that exists on main, updated in the branch only.
    with NetBoxRestClient() as main_client:
        sites = main_client.list("site", {"limit": 1})
    if not sites:
        pytest.skip("needs at least one site on main")
    site = sites[0]
    note = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    with NetBoxRestClient(branch=branch) as client:
        client.patch("site", site["id"], {"description": note})

    diff = write.get_branch_diff(
        branch, object_type="dcim.site", action="update", limit=1000
    )

    entry = next(e for e in diff["results"] if e["object_id"] == site["id"])
    assert entry["changes"]["description"] == {
        "before": site["description"],
        "after": note,
    }


def test_get_branch_diff_on_an_unknown_branch_is_not_found():
    with pytest.raises(NetBoxNotFoundError, match="schema_id"):
        write.get_branch_diff("zzzzzzzz")


def _unused_main_tenant() -> dict:
    """A tenant on main nothing is assigned to, safe to delete in a branch."""
    with NetBoxRestClient() as main_client:
        for t in main_client.list("tenant", {"limit": 1000}):
            if not any(v for k, v in t.items() if k.endswith("_count")):
                return t
    pytest.skip("needs a tenant on main that nothing is assigned to")


def test_get_branch_diff_leaves_out_objects_created_then_deleted():
    # NETBOX-144: netbox_branching keeps an object created then deleted in
    # the branch as a `create` with no data; the diff must not show it.
    main_tenant = _unused_main_tenant()
    s = uuid.uuid4().hex[:8]
    branch = write.create_branch(f"netbox-mcp-test-144-{s}")["schema_id"]
    with NetBoxRestClient(branch=branch) as client:
        mfr = client.create("manufacturer", {"name": f"m-{s}", "slug": f"m-{s}"})
        role = client.create("device_role", {"name": f"r-{s}", "slug": f"r-{s}"})
        site = client.create("site", {"name": f"s-{s}", "slug": f"s-{s}"})
        dt = client.create(
            "device_type",
            {"manufacturer": mfr["id"], "model": f"dt-{s}", "slug": f"dt-{s}"},
        )
        for i in range(3):
            client.create(
                "interface_template",
                {"device_type": dt["id"], "name": f"eth{i}", "type": "1000base-t"},
            )
        device = {
            "name": f"d-{s}",
            "device_type": dt["id"],
            "role": role["id"],
            "site": site["id"],
        }
        # Deleted then recreated: the first device and its 3 interfaces
        # must not show up.
        first = client.create("device", device)
        client.delete("device", first["id"])
        second = client.create("device", device)
        # create -> update -> delete: nothing to show.
        tmp = client.create("site", {"name": f"tmp-{s}", "slug": f"tmp-{s}"})
        client.patch("site", tmp["id"], {"description": "short-lived"})
        client.delete("site", tmp["id"])
        # On main, updated then deleted in the branch: a single delete.
        client.patch("tenant", main_tenant["id"], {"description": "doomed"})
        client.delete("tenant", main_tenant["id"])

    diff = write.get_branch_diff(branch, limit=1000)

    by_type: dict[str, list] = {}
    for entry in diff["results"]:
        by_type.setdefault(entry["object_type"], []).append(entry)
    assert all(e["data"] for e in diff["results"] if e["action"] == "create")
    assert [e["object_id"] for e in by_type["dcim.device"]] == [second["id"]]
    assert len(by_type["dcim.interface"]) == 3
    assert len(by_type["dcim.interfacetemplate"]) == 3
    assert [e["object_id"] for e in by_type["dcim.site"]] == [site["id"]]
    assert [e["object_id"] for e in by_type["dcim.manufacturer"]] == [mfr["id"]]
    assert [(e["object_id"], e["action"]) for e in by_type["tenancy.tenant"]] == [
        (main_tenant["id"], "delete")
    ]
    # manufacturer, role, site, device type, 3 templates, device, 3 interfaces
    assert diff["summary"] == {"create": 11, "update": 0, "delete": 1}
    assert diff["count"] == 12


@pytest.mark.parametrize(
    "name",
    [
        "Test - ascii seulement",
        "Test – en-dash",
        "Test / slash",
        "Test accentué éàç",
        "Test – combiné / éàç",
    ],
)
def test_create_branch_accepts_non_ascii_and_slashes(name):
    # NETBOX-147: an en-dash and a `/` were suspected of breaking create_branch.
    full_name = f"{name} {uuid.uuid4().hex[:6]}"

    created = write.create_branch(full_name)

    assert created["name"] == full_name
    assert created["status"]["value"] == "ready"
    listed = write.list_branches(limit=1000)["results"]
    assert [b["name"] for b in listed if b["schema_id"] == created["schema_id"]] == [
        full_name
    ]


def test_create_branch_refusal_says_what_netbox_answered():
    with pytest.raises(NetBoxValidationError, match=r"\(400\): .*100 characters"):
        write.create_branch("x" * 101)
