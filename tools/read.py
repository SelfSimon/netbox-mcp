"""Read-only MCP tools: list/get for site, device, interface, ip_address, and
vlan — the first slice of read tools, matching the resources covered by
`schemas/filters.py` and `client/registry.py`'s DCIM + IPAM slice. Every
other registered resource gets a matching pair the same way, as its filter
schema is added (see docs/OBJECT_COVERAGE.md).

Each tool builds its own `NetBoxRestClient` from the calling user's own
token (`netbox_mcp.auth.get_current_token`), never a shared service
account. Reads see `main` unless the caller passes `branch` (a schema_id),
in which case the request carries `X-NetBox-Branch` and sees the branch's
state, writes included (NETBOX-145).

Results are shaped by `tools/response.py`: `list_*` tools return an envelope
(`count`, `returned`, `truncated`, `next_offset`, `results`) and every
result stays under the response size cap.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from client.config import get_settings
from client.rest import NetBoxRestClient
from netbox_mcp.auth import get_current_token
from schemas.filters import (
    DeviceFilter,
    InterfaceFilter,
    IPAddressFilter,
    SiteFilter,
    VLANFilter,
)
from tools.response import list_response, object_response, selection_params

if TYPE_CHECKING:
    from fastmcp import FastMCP


def _client(branch: str | None = None) -> NetBoxRestClient:
    settings = replace(get_settings(), netbox_api_token=get_current_token())
    return NetBoxRestClient(settings, branch=branch or None)


def list_sites(
    filters: SiteFilter | None = None, branch: str | None = None
) -> dict[str, Any]:
    """List NetBox sites, optionally narrowed by filters.

    Returns `{count, returned, offset, truncated, next_offset, results}`:
    `count` is the total matching in NetBox, and `truncated` means there is
    more — continue from `next_offset`. Defaults to the first 50 results;
    pass `limit` (max 1000) / `offset` to page, `ordering` (e.g.
    "-created") to sort, and `brief` or `fields` to get smaller objects.

    Pass `branch`, the `schema_id` of a branch from list_branches(), to read
    as of that branch, its unmerged writes included; without it, reads
    `main`.
    """
    with _client(branch) as client:
        return list_response(
            client.list_page("site", (filters or SiteFilter()).to_params())
        )


def get_site(
    site_id: int,
    brief: bool = False,
    fields: list[str] | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Get a single NetBox site by ID.

    Pass `fields` (e.g. ["id", "name"]) or `brief=True` to get only part
    of the object. Pass `branch`, the `schema_id` of a branch from
    list_branches(), to read as of that branch, its unmerged writes
    included; without it, reads `main`.
    """
    with _client(branch) as client:
        return object_response(
            client.get("site", site_id, selection_params(brief, fields))
        )


def list_devices(
    filters: DeviceFilter | None = None, branch: str | None = None
) -> dict[str, Any]:
    """List NetBox devices, optionally narrowed by filters.

    Returns `{count, returned, offset, truncated, next_offset, results}`:
    `count` is the total matching in NetBox, and `truncated` means there is
    more — continue from `next_offset`. Defaults to the first 50 results;
    pass `limit` (max 1000) / `offset` to page, `ordering` (e.g.
    "-created") to sort, and `brief` or `fields` to get smaller objects.

    Pass `branch`, the `schema_id` of a branch from list_branches(), to read
    as of that branch, its unmerged writes included; without it, reads
    `main`.
    """
    with _client(branch) as client:
        return list_response(
            client.list_page("device", (filters or DeviceFilter()).to_params())
        )


def get_device(
    device_id: int,
    brief: bool = False,
    fields: list[str] | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Get a single NetBox device by ID.

    Pass `fields` (e.g. ["id", "name"]) or `brief=True` to get only part
    of the object. Pass `branch`, the `schema_id` of a branch from
    list_branches(), to read as of that branch, its unmerged writes
    included; without it, reads `main`.
    """
    with _client(branch) as client:
        return object_response(
            client.get("device", device_id, selection_params(brief, fields))
        )


def list_interfaces(
    filters: InterfaceFilter | None = None, branch: str | None = None
) -> dict[str, Any]:
    """List NetBox device interfaces, optionally narrowed by filters.

    Returns `{count, returned, offset, truncated, next_offset, results}`:
    `count` is the total matching in NetBox, and `truncated` means there is
    more — continue from `next_offset`. Defaults to the first 50 results;
    pass `limit` (max 1000) / `offset` to page, `ordering` (e.g.
    "-created") to sort, and `brief` or `fields` to get smaller objects.

    Pass `branch`, the `schema_id` of a branch from list_branches(), to read
    as of that branch, its unmerged writes included; without it, reads
    `main`.
    """
    with _client(branch) as client:
        return list_response(
            client.list_page("interface", (filters or InterfaceFilter()).to_params())
        )


def get_interface(
    interface_id: int,
    brief: bool = False,
    fields: list[str] | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Get a single NetBox device interface by ID.

    Pass `fields` (e.g. ["id", "name"]) or `brief=True` to get only part
    of the object. Pass `branch`, the `schema_id` of a branch from
    list_branches(), to read as of that branch, its unmerged writes
    included; without it, reads `main`.
    """
    with _client(branch) as client:
        return object_response(
            client.get("interface", interface_id, selection_params(brief, fields))
        )


def list_ip_addresses(
    filters: IPAddressFilter | None = None, branch: str | None = None
) -> dict[str, Any]:
    """List NetBox IP addresses, optionally narrowed by filters.

    Returns `{count, returned, offset, truncated, next_offset, results}`:
    `count` is the total matching in NetBox, and `truncated` means there is
    more — continue from `next_offset`. Defaults to the first 50 results;
    pass `limit` (max 1000) / `offset` to page, `ordering` (e.g.
    "-created") to sort, and `brief` or `fields` to get smaller objects.

    Pass `branch`, the `schema_id` of a branch from list_branches(), to read
    as of that branch, its unmerged writes included; without it, reads
    `main`.
    """
    with _client(branch) as client:
        return list_response(
            client.list_page("ip_address", (filters or IPAddressFilter()).to_params())
        )


def get_ip_address(
    ip_address_id: int,
    brief: bool = False,
    fields: list[str] | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Get a single NetBox IP address by ID.

    Pass `fields` (e.g. ["id", "name"]) or `brief=True` to get only part
    of the object. Pass `branch`, the `schema_id` of a branch from
    list_branches(), to read as of that branch, its unmerged writes
    included; without it, reads `main`.
    """
    with _client(branch) as client:
        return object_response(
            client.get("ip_address", ip_address_id, selection_params(brief, fields))
        )


def list_vlans(
    filters: VLANFilter | None = None, branch: str | None = None
) -> dict[str, Any]:
    """List NetBox VLANs, optionally narrowed by filters.

    Returns `{count, returned, offset, truncated, next_offset, results}`:
    `count` is the total matching in NetBox, and `truncated` means there is
    more — continue from `next_offset`. Defaults to the first 50 results;
    pass `limit` (max 1000) / `offset` to page, `ordering` (e.g.
    "-created") to sort, and `brief` or `fields` to get smaller objects.

    Pass `branch`, the `schema_id` of a branch from list_branches(), to read
    as of that branch, its unmerged writes included; without it, reads
    `main`.
    """
    with _client(branch) as client:
        return list_response(
            client.list_page("vlan", (filters or VLANFilter()).to_params())
        )


def get_vlan(
    vlan_id: int,
    brief: bool = False,
    fields: list[str] | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Get a single NetBox VLAN by ID.

    Pass `fields` (e.g. ["id", "name"]) or `brief=True` to get only part
    of the object. Pass `branch`, the `schema_id` of a branch from
    list_branches(), to read as of that branch, its unmerged writes
    included; without it, reads `main`.
    """
    with _client(branch) as client:
        return object_response(
            client.get("vlan", vlan_id, selection_params(brief, fields))
        )


_READ_TOOLS = (
    list_sites,
    get_site,
    list_devices,
    get_device,
    list_interfaces,
    get_interface,
    list_ip_addresses,
    get_ip_address,
    list_vlans,
    get_vlan,
)


_READ_ANNOTATIONS = ToolAnnotations(read_only_hint=True, idempotent_hint=True)


def register(mcp: FastMCP) -> None:
    """Register every read tool on `mcp`."""
    for fn in _READ_TOOLS:
        mcp.add_tool(Tool.from_function(fn, annotations=_READ_ANNOTATIONS))
