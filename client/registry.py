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
vlan). Resources marked `branchable=False`, or with a `read_only` reason,
are read-only through the MCP. Plugin resources (NETBOX-117) are entries
like any other, under `plugins/`; their label names the plugin.
See docs/OBJECT_COVERAGE.md for tracking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """Describes a NetBox resource exposed by the client.

    rest_path: NetBox REST API path, relative to /api/ (e.g. "dcim/devices/").
    label: human-readable NetBox name, surfaced by search_resources().
    branchable: False when netbox_branching does not version the model (no
        change logging, or exempted by the plugin). The plugin ignores
        `X-NetBox-Branch` for these, so a write would land directly on
        `main`: the client refuses every write to them (NETBOX-142) and
        they are created by hand in the NetBox UI. Reads are unaffected.
        Checked against a live NetBox by
        tests/integration/test_rest_integration.py.
    read_only: why the MCP never writes this resource although
        netbox_branching versions it (e.g. a file upload, which the JSON
        REST payload cannot carry); empty when it is writable. Reads are
        unaffected.
    """

    rest_path: str
    label: str
    branchable: bool = True
    read_only: str = ""

    @property
    def writable(self) -> bool:
        """True when write_resource() and the client's writes accept it."""
        return self.branchable and not self.read_only


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
    # Component templates: defined once on a device type / module type,
    # instantiated by NetBox on every new device / module of that type.
    "console_port_template": ModelSpec(
        "dcim/console-port-templates/", "Console port template"
    ),
    "console_server_port_template": ModelSpec(
        "dcim/console-server-port-templates/", "Console server port template"
    ),
    "power_port_template": ModelSpec(
        "dcim/power-port-templates/", "Power port template"
    ),
    "power_outlet_template": ModelSpec(
        "dcim/power-outlet-templates/", "Power outlet template"
    ),
    "interface_template": ModelSpec("dcim/interface-templates/", "Interface template"),
    "front_port_template": ModelSpec(
        "dcim/front-port-templates/", "Front port template"
    ),
    "rear_port_template": ModelSpec("dcim/rear-port-templates/", "Rear port template"),
    "module_bay_template": ModelSpec(
        "dcim/module-bay-templates/", "Module bay template"
    ),
    "device_bay_template": ModelSpec(
        "dcim/device-bay-templates/", "Device bay template"
    ),
    "inventory_item_template": ModelSpec(
        "dcim/inventory-item-templates/", "Inventory item template"
    ),
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
    "custom_field": ModelSpec(
        "extras/custom-fields/", "Custom field", branchable=False
    ),
    "custom_field_choice_set": ModelSpec(
        "extras/custom-field-choice-sets/", "Custom field choice set", branchable=False
    ),
    "custom_link": ModelSpec("extras/custom-links/", "Custom link", branchable=False),
    "config_context": ModelSpec("extras/config-contexts/", "Config context"),
    "config_template": ModelSpec("extras/config-templates/", "Config template"),
    "export_template": ModelSpec(
        "extras/export-templates/", "Export template", branchable=False
    ),
    "saved_filter": ModelSpec(
        "extras/saved-filters/", "Saved filter", branchable=False
    ),
    "webhook": ModelSpec("extras/webhooks/", "Webhook", branchable=False),
    "event_rule": ModelSpec("extras/event-rules/", "Event rule", branchable=False),
    "notification_group": ModelSpec(
        "extras/notification-groups/", "Notification group", branchable=False
    ),
    "journal_entry": ModelSpec("extras/journal-entries/", "Journal entry"),
    "image_attachment": ModelSpec("extras/image-attachments/", "Image attachment"),
    "bookmark": ModelSpec("extras/bookmarks/", "Bookmark", branchable=False),
    "script": ModelSpec("extras/scripts/", "Script", branchable=False),
    # -- Users / core --------------------------------------------------------
    "user": ModelSpec("users/users/", "User", branchable=False),
    "group": ModelSpec("users/groups/", "Group", branchable=False),
    "permission": ModelSpec("users/permissions/", "Permission", branchable=False),
    "token": ModelSpec("users/tokens/", "Token", branchable=False),
    # Ownership (NetBox 4.5+): the `owner` field on devices and other objects.
    "owner": ModelSpec("users/owners/", "Owner", branchable=False),
    "owner_group": ModelSpec("users/owner-groups/", "Owner group", branchable=False),
    "data_source": ModelSpec("core/data-sources/", "Data source", branchable=False),
    "data_file": ModelSpec("core/data-files/", "Data file", branchable=False),
    "job": ModelSpec("core/jobs/", "Job", branchable=False),
    # -- Plugins (NETBOX-117) -------------------------------------------
    # netbox_security: firewall/NAT/zone objects, all versioned by
    # netbox_branching. Both *-rule-*-settings endpoints answer 500 on
    # every read in 1.5.11 (plugin bug, see docs/OBJECT_COVERAGE.md).
    "security_address": ModelSpec(
        "plugins/netbox-security/addresses/", "Address (netbox_security)"
    ),
    "security_address_assignment": ModelSpec(
        "plugins/netbox-security/address-assignments/",
        "Address assignment (netbox_security)",
    ),
    "security_address_list": ModelSpec(
        "plugins/netbox-security/address-lists/", "Address list (netbox_security)"
    ),
    "security_address_list_assignment": ModelSpec(
        "plugins/netbox-security/address-list-assignments/",
        "Address list assignment (netbox_security)",
    ),
    "security_address_set": ModelSpec(
        "plugins/netbox-security/address-sets/", "Address set (netbox_security)"
    ),
    "security_address_set_assignment": ModelSpec(
        "plugins/netbox-security/address-set-assignments/",
        "Address set assignment (netbox_security)",
    ),
    "security_application": ModelSpec(
        "plugins/netbox-security/applications/", "Application (netbox_security)"
    ),
    "security_application_assignment": ModelSpec(
        "plugins/netbox-security/application-assignments/",
        "Application assignment (netbox_security)",
    ),
    "security_application_item": ModelSpec(
        "plugins/netbox-security/application-items/",
        "Application item (netbox_security)",
    ),
    "security_application_set": ModelSpec(
        "plugins/netbox-security/application-sets/", "Application set (netbox_security)"
    ),
    "security_application_set_assignment": ModelSpec(
        "plugins/netbox-security/application-set-assignments/",
        "Application set assignment (netbox_security)",
    ),
    "security_custom_prefix": ModelSpec(
        "plugins/netbox-security/custom-prefixes/", "Custom prefix (netbox_security)"
    ),
    "security_zone": ModelSpec(
        "plugins/netbox-security/security-zones/", "Security zone (netbox_security)"
    ),
    "security_zone_assignment": ModelSpec(
        "plugins/netbox-security/security-zone-assignments/",
        "Security zone assignment (netbox_security)",
    ),
    "security_zone_policy": ModelSpec(
        "plugins/netbox-security/security-zone-policies/",
        "Security zone policy (netbox_security)",
    ),
    "firewall_filter": ModelSpec(
        "plugins/netbox-security/firewall-filters/", "Firewall filter (netbox_security)"
    ),
    "firewall_filter_assignment": ModelSpec(
        "plugins/netbox-security/firewall-filter-assignments/",
        "Firewall filter assignment (netbox_security)",
    ),
    "firewall_filter_rule": ModelSpec(
        "plugins/netbox-security/firewall-filter-rules/",
        "Firewall filter rule (netbox_security)",
    ),
    "firewall_filter_rule_from_setting": ModelSpec(
        "plugins/netbox-security/firewall-filter-rule-from-settings/",
        "Firewall filter rule from setting (netbox_security)",
    ),
    "firewall_filter_rule_then_setting": ModelSpec(
        "plugins/netbox-security/firewall-filter-rule-then-settings/",
        "Firewall filter rule then setting (netbox_security)",
    ),
    "nat_pool": ModelSpec(
        "plugins/netbox-security/nat-pools/", "NAT pool (netbox_security)"
    ),
    "nat_pool_assignment": ModelSpec(
        "plugins/netbox-security/nat-pool-assignments/",
        "NAT pool assignment (netbox_security)",
    ),
    "nat_pool_member": ModelSpec(
        "plugins/netbox-security/nat-pool-members/", "NAT pool member (netbox_security)"
    ),
    "nat_rule": ModelSpec(
        "plugins/netbox-security/nat-rules/", "NAT rule (netbox_security)"
    ),
    "nat_rule_assignment": ModelSpec(
        "plugins/netbox-security/nat-rule-assignments/",
        "NAT rule assignment (netbox_security)",
    ),
    "nat_rule_set": ModelSpec(
        "plugins/netbox-security/nat-rule-sets/", "NAT rule set (netbox_security)"
    ),
    "nat_rule_set_assignment": ModelSpec(
        "plugins/netbox-security/nat-rule-set-assignments/",
        "NAT rule set assignment (netbox_security)",
    ),
    "policer": ModelSpec(
        "plugins/netbox-security/policers/", "Policer (netbox_security)"
    ),
    "policer_assignment": ModelSpec(
        "plugins/netbox-security/policer-assignments/",
        "Policer assignment (netbox_security)",
    ),
    "device_view": ModelSpec(
        "plugins/device_view/device-view/", "Device view (netbox_device_view)"
    ),
    "attachment": ModelSpec(
        "plugins/netbox-attachments/netbox-attachments/",
        "Attachment (netbox_attachments)",
        read_only=(
            "an attachment is a file upload, which this MCP's JSON payloads "
            "cannot carry"
        ),
    ),
    "attachment_assignment": ModelSpec(
        "plugins/netbox-attachments/netbox-attachment-assignments/",
        "Attachment assignment (netbox_attachments)",
    ),
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
