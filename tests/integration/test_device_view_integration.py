"""Integration tests for build_device_view() (NETBOX-150).

The stylename check compares our copy of the plugin's derivation with the
plugin itself: its stylename helper is only reachable from a logged-in UI
session (and the rendered-layout API needs a YAML layout), so the test
runs `get_stylenames_for_device_type()` inside the NetBox container with
`docker exec`. It skips when that container isn't reachable — set
`NETBOX_CONTAINER` if yours isn't named `netbox-docker-netbox-1`.
"""

import json
import os
import shutil
import subprocess
import uuid

import pytest

from client.exceptions import NetBoxNotFoundError
from client.rest import NetBoxRestClient
from tools import write
from tools.device_view import _ports, build_device_view
from tools.device_view_layout import LayoutSection

pytestmark = pytest.mark.integration

_CONTAINER = os.environ.get("NETBOX_CONTAINER", "netbox-docker-netbox-1")

# Run by `manage.py shell` in the container: the plugin's stylenames for
# every device type that has a device view.
_PLUGIN_SCRIPT = """
import json
from netbox_device_view.models import DeviceView
from netbox_device_view.utils import get_stylenames_for_device_type
ids = sorted(set(DeviceView.objects.values_list("device_type_id", flat=True)))
print("@@" + json.dumps({i: get_stylenames_for_device_type(i) for i in ids}))
"""

_KINDS = {
    "Interface": "interface",
    "Console Port": "console_port",
    "Front Port": "front_port",
    "Rear Port": "rear_port",
}


def _plugin_stylenames() -> dict[str, list[dict]]:
    if not shutil.which("docker"):
        pytest.skip("docker is not available")
    done = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            _CONTAINER,
            "/opt/netbox/venv/bin/python",
            "/opt/netbox/netbox/manage.py",
            "shell",
        ],
        input=_PLUGIN_SCRIPT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    if done.returncode != 0:
        pytest.skip(f"cannot run the plugin in {_CONTAINER}: {done.stderr[-300:]}")
    line = next(
        (line for line in done.stdout.splitlines() if line.startswith("@@")), None
    )
    assert line, done.stdout[-500:]
    return json.loads(line[2:])


def test_stylenames_match_the_plugin_for_every_device_view():
    plugin = _plugin_stylenames()
    if not plugin:
        pytest.skip("no device view on main to compare with")

    with NetBoxRestClient() as client:
        for device_type, expected in plugin.items():
            ours = [
                (port.name, port.kind, port.stylename)
                for port in _ports(client, int(device_type))
            ]
            theirs = [
                (item["name"], _KINDS[item["kind"]], item["stylename"])
                for item in expected
            ]
            assert ours == theirs, f"device type {device_type}"


@pytest.fixture(scope="module")
def branch() -> str:
    name = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    return write.create_branch(name, "netbox-mcp device view integration test")[
        "schema_id"
    ]


@pytest.fixture(scope="module")
def switch_type(branch: str) -> int:
    """A 1U device type with 8 copper ports, 2 SFP+ uplinks, a console port
    and a virtual interface (never drawn), created in `branch`."""
    suffix = uuid.uuid4().hex[:8]
    with NetBoxRestClient(branch=branch) as client:
        manufacturer = client.create(
            "manufacturer", {"name": f"mcp-dv-{suffix}", "slug": f"mcp-dv-{suffix}"}
        )
        device_type = client.create(
            "device_type",
            {
                "manufacturer": manufacturer["id"],
                "model": f"mcp-dv-{suffix}",
                "slug": f"mcp-dv-{suffix}",
                "u_height": 1,
            },
        )
        templates = [
            {"name": f"GigabitEthernet1/0/{i}", "type": "1000base-t"}
            for i in range(1, 9)
        ]
        templates += [
            {"name": f"TenGigabitEthernet1/1/{i}", "type": "10gbase-x-sfpp"}
            for i in (1, 2)
        ]
        templates.append({"name": "Vlan1", "type": "virtual"})
        client.create_many(
            "interface_template",
            [{"device_type": device_type["id"], **t} for t in templates],
        )
        client.create(
            "console_port_template",
            {"device_type": device_type["id"], "name": "Console", "type": "rj-45"},
        )
    return device_type["id"]


SECTIONS = [
    LayoutSection(blank=2),
    LayoutSection(ports=["GigabitEthernet1/0/1-8"]),
    LayoutSection(spacer=1),
    LayoutSection(ports=["TenGigabitEthernet1/1/1-2"]),
    LayoutSection(spacer=1),
    LayoutSection(ports=["Console"], pattern="all"),
    LayoutSection(blank=2),
]


def test_build_device_view_creates_then_patches_the_view_in_the_branch(
    branch, switch_type
):
    preview = build_device_view(switch_type, sections=SECTIONS, branch=branch)
    assert preview["grid"] == [
        (
            "x x gigabitethernet0-1 gigabitethernet0-3 gigabitethernet0-5 "
            "gigabitethernet0-7 . tengigabitethernet1-1 . console z z"
        ),
        (
            "x x gigabitethernet0-2 gigabitethernet0-4 gigabitethernet0-6 "
            "gigabitethernet0-8 . tengigabitethernet1-2 . . z z"
        ),
    ]
    assert preview["unplaced"] == []
    assert preview["placed"] == 11

    created = build_device_view(
        switch_type, sections=SECTIONS, branch=branch, dry_run=False
    )
    assert created["action"] == "created"

    with NetBoxRestClient(branch=branch) as client:
        view = client.get("device_view", created["device_view"]["id"])
        assert view["grid_template_area"] == preview["grid_template_area"]
    # The view only exists in the branch.
    # A GET, not a filtered list: netbox_device_view ignores filters.
    with NetBoxRestClient() as client, pytest.raises(NetBoxNotFoundError):
        client.get("device_view", view["id"])

    narrower = SECTIONS[:2]
    patched = build_device_view(
        switch_type, sections=narrower, branch=branch, dry_run=False
    )
    assert patched["action"] == "patched"
    assert patched["device_view"]["id"] == created["device_view"]["id"]
    assert len(patched["unplaced"]) == 3


def test_build_device_view_refuses_without_a_description(branch, switch_type):
    with pytest.raises(ValueError, match="never guesses") as exc:
        build_device_view(switch_type, branch=branch)

    assert "GigabitEthernet1/0/1 (interface)" in str(exc.value)
    assert "Vlan1" not in str(exc.value)
