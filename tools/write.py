"""Write MCP tools: create/update for device and interface, IP address
assignment, and netbox_branching branch management (create + list only —
no merge/sync/revert/archive, see client/branches.py).

Every create/update tool takes a `branch`: the schema_id of an active
netbox_branching branch (obtained from create_branch()), scoping the write
via `X-NetBox-Branch` per client/rest.py's branch-first design — nothing
here ever writes directly to `main`.

Each tool builds its own `NetBoxRestClient` from the calling user's own
token (`netbox_mcp.auth.get_current_token`), never a shared service
account, same as tools/read.py.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from client import branches as branch_client
from client.config import get_settings
from client.rest import NetBoxRestClient
from netbox_mcp.auth import get_current_token
from schemas.writes import (
    DeviceCreate,
    DeviceUpdate,
    InterfaceCreate,
    InterfaceUpdate,
    IPAddressAssign,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP


def _client(branch: str | None = None) -> NetBoxRestClient:
    settings = replace(get_settings(), netbox_api_token=get_current_token())
    return NetBoxRestClient(settings, branch=branch)


def create_device(payload: DeviceCreate, branch: str) -> dict[str, Any]:
    """Create a device inside a netbox_branching branch.

    `branch` should be the schema_id you already obtained from
    create_branch() for this task — reuse the same branch across every
    related write, don't create a new one per call.
    """
    with _client(branch) as client:
        return client.create("device", payload.to_payload())


def update_device(device_id: int, payload: DeviceUpdate, branch: str) -> dict[str, Any]:
    """Partially update a device inside a netbox_branching branch.

    `branch` should be the schema_id you already obtained from
    create_branch() for this task — reuse the same branch across every
    related write, don't create a new one per call.
    """
    with _client(branch) as client:
        return client.patch("device", device_id, payload.to_payload())


def create_interface(payload: InterfaceCreate, branch: str) -> dict[str, Any]:
    """Create a device interface inside a netbox_branching branch.

    `branch` should be the schema_id you already obtained from
    create_branch() for this task — reuse the same branch across every
    related write, don't create a new one per call.
    """
    with _client(branch) as client:
        return client.create("interface", payload.to_payload())


def update_interface(
    interface_id: int, payload: InterfaceUpdate, branch: str
) -> dict[str, Any]:
    """Partially update a device interface inside a netbox_branching branch.

    `branch` should be the schema_id you already obtained from
    create_branch() for this task — reuse the same branch across every
    related write, don't create a new one per call.
    """
    with _client(branch) as client:
        return client.patch("interface", interface_id, payload.to_payload())


def assign_ip_address(payload: IPAddressAssign, branch: str) -> dict[str, Any]:
    """Create an IP address already assigned to an interface, inside a
    netbox_branching branch.

    `branch` should be the schema_id you already obtained from
    create_branch() for this task — reuse the same branch across every
    related write, don't create a new one per call.
    """
    with _client(branch) as client:
        return client.create("ip_address", payload.to_payload())


def create_branch(name: str, description: str = "") -> dict[str, Any]:
    """Create a netbox_branching branch and wait for it to become ready.

    Call this ONCE per logical task or change-set, not once per write. If
    you are about to make several related writes (e.g. "add these 3
    devices", "create a device and its interfaces and IP"), create a
    single branch here, then pass its `schema_id` to every create_device /
    update_device / create_interface / update_interface / assign_ip_address
    call in that task. Creating a new branch per individual write causes
    branch proliferation that a human then has to clean up in the NetBox
    UI — check list_branches() first for an existing "ready"-status branch
    from this task before calling this again.

    Returns the ready branch object; its `schema_id` is the `branch`
    argument the other write tools need. Merging, syncing, reverting, or
    archiving a branch is deliberately not exposed here — that stays a
    human action taken from the NetBox UI (see client/branches.py).
    """
    with _client() as client:
        created = branch_client.create_branch(client, name, description)
        return branch_client.wait_until_ready(client, created["id"])


def list_branches() -> list[dict[str, Any]]:
    """List netbox_branching branches.

    Before calling create_branch(), check here for an existing
    "ready"-status branch you already created for the current task, and
    reuse its schema_id instead of creating a new one.
    """
    with _client() as client:
        return branch_client.list_branches(client)


_CREATE_ANNOTATIONS = ToolAnnotations(destructiveHint=False, idempotentHint=False)
_UPDATE_ANNOTATIONS = ToolAnnotations(destructiveHint=True, idempotentHint=True)
_BRANCH_LIST_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, idempotentHint=True)

_WRITE_TOOLS = (
    (create_device, _CREATE_ANNOTATIONS),
    (update_device, _UPDATE_ANNOTATIONS),
    (create_interface, _CREATE_ANNOTATIONS),
    (update_interface, _UPDATE_ANNOTATIONS),
    (assign_ip_address, _CREATE_ANNOTATIONS),
    (create_branch, _CREATE_ANNOTATIONS),
    (list_branches, _BRANCH_LIST_ANNOTATIONS),
)


def register(mcp: "FastMCP") -> None:
    """Register every write tool on `mcp`."""
    for fn, tool_annotations in _WRITE_TOOLS:
        mcp.add_tool(Tool.from_function(fn, annotations=tool_annotations))
