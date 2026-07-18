"""Registry of NetBox resources exposed by the data client.

A single resource name ("device", "ip_address", ...) resolves to the NetBox
REST API path used for every operation (list/get/count/create/update/patch/
delete) — the client is REST-only, so this is a flat name -> path mapping,
not a Django model reference.

Target scope: every NetBox object type reachable over the REST API (DCIM,
IPAM, virtualization, circuits, tenancy, extras, ...) — there is no
permanent object-type allow-list here. What's registered below is current
implementation progress, not a scoping decision: DCIM + IPAM first,
extended incrementally as more tools are added. Access control is
NetBox's own job (per-user token permissions, see
`src/netbox_mcp/auth.py`), not this registry's.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """Describes a NetBox resource exposed by the client.

    rest_path: NetBox REST API path, relative to /api/ (e.g. "dcim/devices/").
    """

    rest_path: str


_REGISTRY: dict[str, ModelSpec] = {
    "site": ModelSpec("dcim/sites/"),
    "device": ModelSpec("dcim/devices/"),
    "device_role": ModelSpec("dcim/device-roles/"),
    "device_type": ModelSpec("dcim/device-types/"),
    "manufacturer": ModelSpec("dcim/manufacturers/"),
    "interface": ModelSpec("dcim/interfaces/"),
    "cable": ModelSpec("dcim/cables/"),
    "rack": ModelSpec("dcim/racks/"),
    "ip_address": ModelSpec("ipam/ip-addresses/"),
    "prefix": ModelSpec("ipam/prefixes/"),
    "vlan": ModelSpec("ipam/vlans/"),
    "vrf": ModelSpec("ipam/vrfs/"),
}


def get_model_spec(resource: str) -> ModelSpec:
    """Resolve a logical resource name to its ModelSpec.

    Raises KeyError (not a NetBoxClientError) if the resource isn't
    registered: this is a programming error on the caller's side (a typo in
    tools/, or tools/ not yet updated for a new resource), not a NetBox
    runtime error to catch on the MCP side.
    """
    return _REGISTRY[resource]


def list_resources() -> list[str]:
    return sorted(_REGISTRY)
