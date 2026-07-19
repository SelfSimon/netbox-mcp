"""Registry of NetBox resources exposed by the data client.

A single resource name ("device", "ip_address", ...) resolves to the NetBox
REST API path used for every operation (list/get/count/create/update/patch/
delete) — the client is REST-only, so this is a flat name -> path mapping,
not a Django model reference.

Target scope: every NetBox object type reachable over the REST API (DCIM,
IPAM, virtualization, circuits, tenancy, extras, ...) — there is no
permanent object-type allow-list here. Registering a resource here is
enough to make it usable through the generic `search_resources`/
`get_resource`/`write_resource` MCP tools (`tools/generic.py`); a resource
only needs a dedicated tool (`tools/read.py`/`tools/write.py`) and Pydantic
schemas once it's high-usage enough to warrant precise validation and
per-action MCP annotations (currently: site, device, interface, ip_address,
vlan). See OBJECT_COVERAGE.md for tracking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """Describes a NetBox resource exposed by the client.

    rest_path: NetBox REST API path, relative to /api/ (e.g. "dcim/devices/").
    label: human-readable NetBox name, surfaced by search_resources().
    """

    rest_path: str
    label: str


_REGISTRY: dict[str, ModelSpec] = {
    # -- DCIM ------------------------------------------------------------
    "site": ModelSpec("dcim/sites/", "Site"),
    "region": ModelSpec("dcim/regions/", "Region"),
    "site_group": ModelSpec("dcim/site-groups/", "Site group"),
    "location": ModelSpec("dcim/locations/", "Location"),
    "rack": ModelSpec("dcim/racks/", "Rack"),
    "rack_role": ModelSpec("dcim/rack-roles/", "Rack role"),
    "rack_reservation": ModelSpec("dcim/rack-reservations/", "Rack reservation"),
    "rack_type": ModelSpec("dcim/rack-types/", "Rack type"),
    "manufacturer": ModelSpec("dcim/manufacturers/", "Manufacturer"),
    "device_type": ModelSpec("dcim/device-types/", "Device type"),
    "module_type": ModelSpec("dcim/module-types/", "Module type"),
    "device_role": ModelSpec("dcim/device-roles/", "Device role"),
    "platform": ModelSpec("dcim/platforms/", "Platform"),
    "device": ModelSpec("dcim/devices/", "Device"),
    "module": ModelSpec("dcim/modules/", "Module"),
    "virtual_chassis": ModelSpec("dcim/virtual-chassis/", "Virtual chassis"),
    "virtual_device_context": ModelSpec(
        "dcim/virtual-device-contexts/", "Virtual device context"
    ),
    "device_bay": ModelSpec("dcim/device-bays/", "Device bay"),
    "module_bay": ModelSpec("dcim/module-bays/", "Module bay"),
    "inventory_item": ModelSpec("dcim/inventory-items/", "Inventory item"),
    "inventory_item_role": ModelSpec(
        "dcim/inventory-item-roles/", "Inventory item role"
    ),
    "interface": ModelSpec("dcim/interfaces/", "Interface"),
    "mac_address": ModelSpec("dcim/mac-addresses/", "MAC address"),
    "console_port": ModelSpec("dcim/console-ports/", "Console port"),
    "console_server_port": ModelSpec(
        "dcim/console-server-ports/", "Console server port"
    ),
    "power_port": ModelSpec("dcim/power-ports/", "Power port"),
    "power_outlet": ModelSpec("dcim/power-outlets/", "Power outlet"),
    "power_panel": ModelSpec("dcim/power-panels/", "Power panel"),
    "power_feed": ModelSpec("dcim/power-feeds/", "Power feed"),
    "front_port": ModelSpec("dcim/front-ports/", "Front port"),
    "rear_port": ModelSpec("dcim/rear-ports/", "Rear port"),
    "cable": ModelSpec("dcim/cables/", "Cable"),
    # -- IPAM --------------------------------------------------------------
    "vrf": ModelSpec("ipam/vrfs/", "VRF"),
    "route_target": ModelSpec("ipam/route-targets/", "Route target"),
    "rir": ModelSpec("ipam/rirs/", "RIR"),
    "aggregate": ModelSpec("ipam/aggregates/", "Aggregate"),
    "ipam_role": ModelSpec("ipam/roles/", "IPAM role"),
    "prefix": ModelSpec("ipam/prefixes/", "Prefix"),
    "ip_range": ModelSpec("ipam/ip-ranges/", "IP range"),
    "ip_address": ModelSpec("ipam/ip-addresses/", "IP address"),
    "vlan": ModelSpec("ipam/vlans/", "VLAN"),
    "vlan_group": ModelSpec("ipam/vlan-groups/", "VLAN group"),
    "asn": ModelSpec("ipam/asns/", "ASN"),
    "asn_range": ModelSpec("ipam/asn-ranges/", "ASN range"),
    "fhrp_group": ModelSpec("ipam/fhrp-groups/", "FHRP group"),
    "fhrp_group_assignment": ModelSpec(
        "ipam/fhrp-group-assignments/", "FHRP group assignment"
    ),
    "service": ModelSpec("ipam/services/", "Service"),
    "service_template": ModelSpec("ipam/service-templates/", "Service template"),
    # -- Virtualization ------------------------------------------------------
    "cluster_type": ModelSpec("virtualization/cluster-types/", "Cluster type"),
    "cluster_group": ModelSpec("virtualization/cluster-groups/", "Cluster group"),
    "cluster": ModelSpec("virtualization/clusters/", "Cluster"),
    "virtual_machine": ModelSpec("virtualization/virtual-machines/", "Virtual machine"),
    "vm_interface": ModelSpec("virtualization/interfaces/", "VM interface"),
    "virtual_disk": ModelSpec("virtualization/virtual-disks/", "Virtual disk"),
    # -- Circuits ------------------------------------------------------------
    "provider": ModelSpec("circuits/providers/", "Provider"),
    "provider_account": ModelSpec("circuits/provider-accounts/", "Provider account"),
    "provider_network": ModelSpec("circuits/provider-networks/", "Provider network"),
    "circuit_type": ModelSpec("circuits/circuit-types/", "Circuit type"),
    "circuit": ModelSpec("circuits/circuits/", "Circuit"),
    "circuit_termination": ModelSpec(
        "circuits/circuit-terminations/", "Circuit termination"
    ),
    "circuit_group": ModelSpec("circuits/circuit-groups/", "Circuit group"),
    "circuit_group_assignment": ModelSpec(
        "circuits/circuit-group-assignments/", "Circuit group assignment"
    ),
    # -- Tenancy -----------------------------------------------------------
    "tenant": ModelSpec("tenancy/tenants/", "Tenant"),
    "tenant_group": ModelSpec("tenancy/tenant-groups/", "Tenant group"),
    "contact": ModelSpec("tenancy/contacts/", "Contact"),
    "contact_group": ModelSpec("tenancy/contact-groups/", "Contact group"),
    "contact_role": ModelSpec("tenancy/contact-roles/", "Contact role"),
    "contact_assignment": ModelSpec(
        "tenancy/contact-assignments/", "Contact assignment"
    ),
    # -- Wireless ----------------------------------------------------------
    "wireless_lan": ModelSpec("wireless/wireless-lans/", "Wireless LAN"),
    "wireless_lan_group": ModelSpec(
        "wireless/wireless-lan-groups/", "Wireless LAN group"
    ),
    "wireless_link": ModelSpec("wireless/wireless-links/", "Wireless link"),
    # -- VPN -----------------------------------------------------------------
    "tunnel": ModelSpec("vpn/tunnels/", "Tunnel"),
    "tunnel_group": ModelSpec("vpn/tunnel-groups/", "Tunnel group"),
    "tunnel_termination": ModelSpec("vpn/tunnel-terminations/", "Tunnel termination"),
    "ike_policy": ModelSpec("vpn/ike-policies/", "IKE policy"),
    "ike_proposal": ModelSpec("vpn/ike-proposals/", "IKE proposal"),
    "ipsec_policy": ModelSpec("vpn/ipsec-policies/", "IPSec policy"),
    "ipsec_profile": ModelSpec("vpn/ipsec-profiles/", "IPSec profile"),
    "ipsec_proposal": ModelSpec("vpn/ipsec-proposals/", "IPSec proposal"),
    "l2vpn": ModelSpec("vpn/l2vpns/", "L2VPN"),
    "l2vpn_termination": ModelSpec("vpn/l2vpn-terminations/", "L2VPN termination"),
    # -- Extras --------------------------------------------------------------
    "tag": ModelSpec("extras/tags/", "Tag"),
    "custom_field": ModelSpec("extras/custom-fields/", "Custom field"),
    "custom_field_choice_set": ModelSpec(
        "extras/custom-field-choice-sets/", "Custom field choice set"
    ),
    "custom_link": ModelSpec("extras/custom-links/", "Custom link"),
    "config_context": ModelSpec("extras/config-contexts/", "Config context"),
    "config_template": ModelSpec("extras/config-templates/", "Config template"),
    "export_template": ModelSpec("extras/export-templates/", "Export template"),
    "saved_filter": ModelSpec("extras/saved-filters/", "Saved filter"),
    "webhook": ModelSpec("extras/webhooks/", "Webhook"),
    "event_rule": ModelSpec("extras/event-rules/", "Event rule"),
    "notification_group": ModelSpec(
        "extras/notification-groups/", "Notification group"
    ),
    "journal_entry": ModelSpec("extras/journal-entries/", "Journal entry"),
    "image_attachment": ModelSpec("extras/image-attachments/", "Image attachment"),
    "bookmark": ModelSpec("extras/bookmarks/", "Bookmark"),
    "script": ModelSpec("extras/scripts/", "Script"),
    # -- Users / core --------------------------------------------------------
    "user": ModelSpec("users/users/", "User"),
    "group": ModelSpec("users/groups/", "Group"),
    "permission": ModelSpec("users/permissions/", "Permission"),
    "token": ModelSpec("users/tokens/", "Token"),
    "data_source": ModelSpec("core/data-sources/", "Data source"),
    "data_file": ModelSpec("core/data-files/", "Data file"),
    "job": ModelSpec("core/jobs/", "Job"),
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


def iter_model_specs() -> list[tuple[str, ModelSpec]]:
    """All registered (resource_name, ModelSpec) pairs, sorted by name.

    Backs search_resources() in tools/generic.py.
    """
    return sorted(_REGISTRY.items())
