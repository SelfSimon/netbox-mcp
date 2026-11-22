"""Reference journey (NETBOX-148): a realistic equipment addition, end to
end, through the MCP tools as a client calls them — run before every
release to prod (see docs/RELEASING.md).

The `journey` fixture plays steps 1 to 5 once, in one branch; each test
then checks a step's outcome. A failure names the step and what differed.
Steps that need a feature not built yet are strict xfails, tied to their
ticket: they start failing (XPASS) as soon as the feature works, as a
reminder to turn them into plain tests.

Every write lands in the journey's branch, which the session deletes at
its end (tests/integration/conftest.py): nothing stays on the instance.

When a bug or a feature of the MCP is fixed, add its scenario here.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from contextlib import contextmanager
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from netbox_mcp.server import mcp

pytestmark = pytest.mark.integration

OWNER_NAME = "netbox-mcp-test"


def call(tool: str, **arguments: Any) -> Any:
    """Call an MCP tool the way a client does, over the MCP protocol."""

    async def _call() -> Any:
        async with Client(mcp) as client:
            result = await client.call_tool(tool, arguments)
            return result.structured_content

    return asyncio.run(_call())


@contextmanager
def step(number: int, label: str):
    """Name the journey step in any failure raised inside it."""
    try:
        yield
    except (AssertionError, ToolError) as exc:
        raise AssertionError(f"Step {number} ({label}): {exc}") from exc


def expect(actual: Any, expected: Any, what: str) -> None:
    assert actual == expected, f"{what}: expected {expected!r}, got {actual!r}"


def _owner_id() -> int | None:
    found = call("get_resource", resource="owner", filters={"name": OWNER_NAME})
    return found["results"][0]["id"] if found["results"] else None


@pytest.fixture(scope="module")
def journey() -> dict[str, Any]:
    s = uuid.uuid4().hex[:6]
    j: dict[str, Any] = {"suffix": s, "owner": _owner_id()}

    with step(1, "create a branch with an accented name"):
        j["branch_name"] = f"netbox-mcp-test parcours réseau – {s}"
        branch = call("create_branch", name=j["branch_name"])
        expect(branch["status"]["value"], "ready", "branch status")
        b = j["branch"] = branch["schema_id"]

    def create(resource: str, data: Any) -> dict[str, Any]:
        return call(
            "write_resource", resource=resource, action="create", branch=b, data=data
        )

    with step(2, "create 2 device types and their interface templates"):
        mfr = create("manufacturer", {"name": f"mfr-{s}", "slug": f"mfr-{s}"})
        j["switch_type"] = create(
            "device_type",
            {"manufacturer": mfr["id"], "model": f"sw-{s}", "slug": f"sw-{s}"},
        )
        j["server_type"] = create(
            "device_type",
            {"manufacturer": mfr["id"], "model": f"srv-{s}", "slug": f"srv-{s}"},
        )
        # One batch per device type (NETBOX-146).
        j["templates"] = {}
        for dt, names in (
            (j["switch_type"], ("eth0", "eth1", "eth2", "eth3")),
            (j["server_type"], ("nic0", "nic1")),
        ):
            batch = create(
                "interface_template",
                [
                    {"device_type": dt["id"], "name": n, "type": "1000base-t"}
                    for n in names
                ],
            )
            expect(batch["count"], len(names), "templates created in a batch")
            j["templates"].update(zip(names, batch["results"], strict=True))

    with step(3, "create racked devices with tenant and owner"):
        j["tenant"] = create("tenant", {"name": f"tenant-{s}", "slug": f"tenant-{s}"})
        site = j["site"] = create("site", {"name": f"site-{s}", "slug": f"site-{s}"})
        j["rack"] = create("rack", {"name": f"rack-{s}", "site": site["id"]})
        role = create("device_role", {"name": f"role-{s}", "slug": f"role-{s}"})

        def device(name: str, device_type: dict, position: int) -> dict[str, Any]:
            payload = {
                "name": name,
                "device_type": device_type["id"],
                "role": role["id"],
                "site": site["id"],
                "rack": j["rack"]["id"],
                "position": position,
                "face": "front",
                "tenant": j["tenant"]["id"],
            }
            if j["owner"]:
                payload["owner"] = j["owner"]
            return call("create_device", payload=payload, branch=b)

        j["device"] = device
        j["switch"] = device(f"sw-{s}", j["switch_type"], 10)
        j["server"] = device(f"srv-{s}", j["server_type"], 20)

    with step(4, "rename interface templates in a batch"):
        renamed = call(
            "write_resource",
            resource="interface_template",
            action="patch",
            branch=b,
            data=[
                {"id": j["templates"][old]["id"], "name": new}
                for old, new in (("eth0", "uplink0"), ("eth1", "uplink1"))
            ],
        )
        expect(
            [r["display"] for r in renamed["results"]],
            ["uplink0", "uplink1"],
            "templates renamed in a batch",
        )

    with step(5, "delete then recreate a device"):
        j["deleted_switch"] = j["switch"]
        call(
            "write_resource",
            resource="device",
            action="delete",
            branch=b,
            object_id=j["switch"]["id"],
            confirm=True,
        )
        j["switch"] = device(f"sw-{s}", j["switch_type"], 10)

    j["diff"] = call("get_branch_diff", branch=b, limit=1000)
    return j


def _entries(j: dict[str, Any], object_type: str) -> list[dict[str, Any]]:
    return [e for e in j["diff"]["results"] if e["object_type"] == object_type]


def _device_id(entry: dict[str, Any]) -> Any:
    """The device of an interface diff entry, an id or a nested object."""
    device = entry["data"].get("device")
    return device.get("id") if isinstance(device, dict) else device


def test_step_1_branch_keeps_its_accented_name(journey):
    with step(1, "create a branch with an accented name"):
        expect(journey["diff"]["branch"], journey["branch_name"], "branch name")


def test_step_3_devices_are_racked_with_their_tenant(journey):
    with step(3, "create racked devices with tenant and owner"):
        for d in (journey["switch"], journey["server"]):
            got = {
                "rack": (d.get("rack") or {}).get("id"),
                "face": (d.get("face") or {}).get("value"),
                "tenant": (d.get("tenant") or {}).get("id"),
            }
            want = {
                "rack": journey["rack"]["id"],
                "face": "front",
                "tenant": journey["tenant"]["id"],
            }
            expect(got, want, f"device {d['name']}")
        positions = [float(journey[k]["position"]) for k in ("switch", "server")]
        expect(positions, [10.0, 20.0], "rack positions")


def test_step_3_devices_have_their_owner(journey):
    if not journey["owner"]:
        pytest.skip(
            f"no owner {OWNER_NAME!r} on main: create it in the NetBox UI "
            "(owners are not versioned by netbox_branching)"
        )
    with step(3, "create racked devices with tenant and owner"):
        for d in (journey["switch"], journey["server"]):
            got = (d.get("owner") or {}).get("id")
            expect(got, journey["owner"], f"owner of {d['name']}")


def test_step_3_devices_inherit_the_interfaces_of_their_type(journey):
    with step(3, "devices inherit their interfaces (diff of the branch)"):
        per_device = Counter(_device_id(e) for e in _entries(journey, "dcim.interface"))
        expect(
            dict(per_device),
            {journey["switch"]["id"]: 4, journey["server"]["id"]: 2},
            "interfaces per device",
        )


def test_step_6_diff_has_exact_net_counts(journey):
    with step(6, "get_branch_diff: exact net counts"):
        # manufacturer, 2 device types, 6 templates, tenant, site, rack,
        # role, 2 devices, 6 interfaces — the deleted switch and its 4
        # interfaces are not part of what the branch changes (NETBOX-144).
        expect(
            journey["diff"]["summary"],
            {"create": 21, "update": 0, "delete": 0},
            "summary",
        )
        expect(
            dict(Counter(e["object_type"] for e in journey["diff"]["results"])),
            {
                "dcim.manufacturer": 1,
                "dcim.devicetype": 2,
                "dcim.interfacetemplate": 6,
                "tenancy.tenant": 1,
                "dcim.site": 1,
                "dcim.rack": 1,
                "dcim.devicerole": 1,
                "dcim.device": 2,
                "dcim.interface": 6,
            },
            "entries per object type",
        )


def test_step_6_diff_has_no_ghost_entry(journey):
    with step(6, "get_branch_diff: no ghost entry"):
        empty = [e for e in journey["diff"]["results"] if not e.get("data")]
        expect(empty, [], "entries without data")
        devices = [e["object_id"] for e in _entries(journey, "dcim.device")]
        assert journey["deleted_switch"]["id"] not in devices, (
            f"deleted device {journey['deleted_switch']['id']} still in the diff"
        )


def test_step_6_diff_shows_the_renamed_templates(journey):
    with step(6, "get_branch_diff: templates under their final name"):
        names = sorted(
            e["data"]["name"] for e in _entries(journey, "dcim.interfacetemplate")
        )
        expect(names, ["eth2", "eth3", "nic0", "nic1", "uplink0", "uplink1"], "names")


def test_step_6_recreated_device_gets_the_renamed_interfaces(journey):
    with step(6, "recreated device: interfaces named after the renamed templates"):
        names = sorted(
            e["data"]["name"]
            for e in _entries(journey, "dcim.interface")
            if _device_id(e) == journey["switch"]["id"]
        )
        expect(names, ["eth2", "eth3", "uplink0", "uplink1"], "interface names")


def test_step_7_reads_in_the_branch_see_the_current_names(journey):
    with step(7, "read the recreated device's interfaces in the branch"):
        found = call(
            "list_interfaces",
            filters={"device_id": journey["switch"]["id"]},
            branch=journey["branch"],
        )
        names = sorted(i["name"] for i in found["results"])
        expect(names, ["eth2", "eth3", "uplink0", "uplink1"], "interface names")


def test_step_7_reads_without_branch_do_not_see_the_branch(journey):
    with step(7, "read the branch's devices on main"):
        for d in (journey["switch"], journey["server"]):
            found = call("list_devices", filters={"name": d["name"]})
            expect(found["results"], [], f"device {d['name']} on main")


def test_step_7_get_device_in_the_branch_sees_its_rack(journey):
    with step(7, "get the recreated device in the branch"):
        d = call(
            "get_device", device_id=journey["switch"]["id"], branch=journey["branch"]
        )
        expect((d.get("rack") or {}).get("id"), journey["rack"]["id"], "rack")


def test_step_7_reads_in_an_unknown_branch_say_so(journey):
    with pytest.raises(ToolError, match=r"no branch with schema_id 'zzzzzzzz'"):
        call("list_devices", branch="zzzzzzzz")


def test_templates_renamed_between_two_devices_read_in_the_branch():
    """NETBOX-145 ticket scenario: a device type with 3 interface templates,
    a device, one template renamed, a second device. In the branch each
    device has the interface names of its creation time; on main, neither
    exists."""
    s = uuid.uuid4().hex[:6]
    with step(1, "create a branch"):
        b = call("create_branch", name=f"netbox-mcp-test-145-{s}")["schema_id"]

    def create(resource: str, data: dict[str, Any]) -> dict[str, Any]:
        return call(
            "write_resource", resource=resource, action="create", branch=b, data=data
        )

    with step(2, "device type with 3 templates, then a first device"):
        mfr = create("manufacturer", {"name": f"mfr-{s}", "slug": f"mfr-{s}"})
        dt = create(
            "device_type",
            {"manufacturer": mfr["id"], "model": f"dt-{s}", "slug": f"dt-{s}"},
        )
        templates = [
            create(
                "interface_template",
                {"device_type": dt["id"], "name": f"eth{i}", "type": "1000base-t"},
            )
            for i in range(3)
        ]
        site = create("site", {"name": f"site-{s}", "slug": f"site-{s}"})
        role = create("device_role", {"name": f"role-{s}", "slug": f"role-{s}"})

        def device(name: str) -> dict[str, Any]:
            payload = {
                "name": name,
                "device_type": dt["id"],
                "role": role["id"],
                "site": site["id"],
            }
            return call("create_device", payload=payload, branch=b)

        first = device(f"d1-{s}")

    with step(3, "rename a template, then a second device"):
        call(
            "write_resource",
            resource="interface_template",
            action="patch",
            branch=b,
            object_id=templates[0]["id"],
            data={"name": "uplink0"},
        )
        second = device(f"d2-{s}")

    with step(4, "read both devices and their interfaces with and without branch"):
        for d, names in (
            (first, ["eth0", "eth1", "eth2"]),
            (second, ["eth1", "eth2", "uplink0"]),
        ):
            got = call("get_device", device_id=d["id"], branch=b)
            expect(got["name"], d["name"], "device read in the branch")
            found = call("list_interfaces", filters={"device_id": d["id"]}, branch=b)
            expect(
                sorted(i["name"] for i in found["results"]),
                names,
                f"interfaces of {d['name']} in the branch",
            )
            # By name: a branch id may also be taken by another object on main.
            on_main = call("list_devices", filters={"name": d["name"]})
            expect(on_main["results"], [], f"{d['name']} on main")


def test_batches_of_templates_are_one_call_and_all_or_nothing():
    """NETBOX-146 ticket scenario: 50 templates created in one call, 24 of
    them renamed in one call, then a batch of 10 with one invalid element:
    nothing of it is written, and the error names the element and field."""
    s = uuid.uuid4().hex[:6]
    with step(1, "create a branch and a device type"):
        b = call("create_branch", name=f"netbox-mcp-test-146-{s}")["schema_id"]

        def write(action: str, data: Any, resource: str = "interface_template"):
            return call(
                "write_resource",
                resource=resource,
                action=action,
                branch=b,
                data=data,
            )

        mfr = write("create", {"name": f"m-{s}", "slug": f"m-{s}"}, "manufacturer")
        dt = write(
            "create",
            {"manufacturer": mfr["id"], "model": f"dt-{s}", "slug": f"dt-{s}"},
            "device_type",
        )

    def names() -> list[str]:
        found = call(
            "get_resource",
            resource="interface_template",
            filters={"device_type_id": dt["id"]},
            limit=1000,
            branch=b,
        )
        return sorted(t["name"] for t in found["results"])

    with step(2, "create 50 templates in one call"):
        created = write(
            "create",
            [
                {"device_type": dt["id"], "name": f"eth{i:02}", "type": "1000base-t"}
                for i in range(50)
            ],
        )
        expect(created["count"], 50, "templates created")
        expect(names(), [f"eth{i:02}" for i in range(50)], "templates in the branch")

    with step(3, "rename 24 templates in one call"):
        renamed = write(
            "patch",
            [
                {"id": t["id"], "name": f"up{i:02}"}
                for i, t in enumerate(created["results"][:24])
            ],
        )
        expect(renamed["count"], 24, "templates renamed")
        want = sorted(
            [f"up{i:02}" for i in range(24)] + [f"eth{i:02}" for i in range(24, 50)]
        )
        expect(names(), want, "names after the rename")

    with step(4, "a batch of 10 with one invalid element writes nothing"):
        bad = [
            {
                "device_type": dt["id"],
                "name": f"bad{i}",
                "type": "nope" if i == 7 else "1000base-t",
            }
            for i in range(10)
        ]
        with pytest.raises(ToolError, match=r"element 7: type: .*nope"):
            write("create", bad)
        expect(names(), want, "names after the rejected batch")
