"""Read-only MCP tools: list/get for site, device, interface, ip_address, and
vlan — the first slice of read tools, matching the resources covered by
`schemas/filters.py` and `client/registry.py`'s DCIM + IPAM slice. Every
other registered resource gets a matching pair the same way, as its filter
schema is added (see docs/OBJECT_COVERAGE.md).

Each tool builds its own `NetBoxRestClient` from the calling user's own
token (`netbox_mcp.auth.get_current_token`), never a shared service
account, and issues an unscoped request (no `netbox_branching` branch):
reads always see `main` as it stands, since branching only matters for the
write tools.
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

if TYPE_CHECKING:
    from fastmcp import FastMCP


def _client() -> NetBoxRestClient:
    settings = replace(get_settings(), netbox_api_token=get_current_token())
    return NetBoxRestClient(settings)


def list_sites(filters: SiteFilter | None = None) -> list[dict[str, Any]]:
    """List NetBox sites, optionally narrowed by filters."""
    with _client() as client:
        return client.list("site", (filters or SiteFilter()).to_params())


def get_site(site_id: int) -> dict[str, Any]:
    """Get a single NetBox site by ID."""
    with _client() as client:
        return client.get("site", site_id)


def list_devices(filters: DeviceFilter | None = None) -> list[dict[str, Any]]:
    """List NetBox devices, optionally narrowed by filters."""
    with _client() as client:
        return client.list("device", (filters or DeviceFilter()).to_params())


def get_device(device_id: int) -> dict[str, Any]:
    """Get a single NetBox device by ID."""
    with _client() as client:
        return client.get("device", device_id)


def list_interfaces(filters: InterfaceFilter | None = None) -> list[dict[str, Any]]:
    """List NetBox device interfaces, optionally narrowed by filters."""
    with _client() as client:
        return client.list("interface", (filters or InterfaceFilter()).to_params())


def get_interface(interface_id: int) -> dict[str, Any]:
    """Get a single NetBox device interface by ID."""
    with _client() as client:
        return client.get("interface", interface_id)


def list_ip_addresses(filters: IPAddressFilter | None = None) -> list[dict[str, Any]]:
    """List NetBox IP addresses, optionally narrowed by filters."""
    with _client() as client:
        return client.list("ip_address", (filters or IPAddressFilter()).to_params())


def get_ip_address(ip_address_id: int) -> dict[str, Any]:
    """Get a single NetBox IP address by ID."""
    with _client() as client:
        return client.get("ip_address", ip_address_id)


def list_vlans(filters: VLANFilter | None = None) -> list[dict[str, Any]]:
    """List NetBox VLANs, optionally narrowed by filters."""
    with _client() as client:
        return client.list("vlan", (filters or VLANFilter()).to_params())


def get_vlan(vlan_id: int) -> dict[str, Any]:
    """Get a single NetBox VLAN by ID."""
    with _client() as client:
        return client.get("vlan", vlan_id)


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


_READ_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


def register(mcp: "FastMCP") -> None:
    """Register every read tool on `mcp`."""
    for fn in _READ_TOOLS:
        mcp.add_tool(Tool.from_function(fn, annotations=_READ_ANNOTATIONS))
