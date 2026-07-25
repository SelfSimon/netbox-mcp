<!--
confluence-sync: true
title: "Couverture des objets"
-->

# Object coverage

Tracks progress toward the project goal stated in [README.md](https://github.com/SelfSimon/netbox-mcp/blob/main/README.md):
every NetBox object type reachable over the REST API should eventually be
usable through MCP. Access control is NetBox's own per-user permissions
(pass-through token, see `src/netbox_mcp/auth.py`), not a restriction
tracked here — this file is about implementation progress, not scope
decisions.

## Legend

- ✅ done — ⬜ not started
- **Registry**: resource name mapped in `client/registry.py`. This alone
  makes the object usable through the generic MCP tools
  (`tools/generic.py`: `search_resources`, `get_resource`,
  `write_resource`) — no read filter, write schema, or dedicated tool
  required.
- **Read filter**: Pydantic filter schema in `schemas/filters.py`
- **Write schema**: Pydantic create/update payload(s) in `schemas/writes.py`
- **Dedicated tool**: MCP tool exposed in `tools/read.py`/`tools/write.py`
  with typed schemas and precise per-action MCP annotations — reserved for
  high-usage objects (currently site, device, interface, ip_address,
  vlan). Everything else with a ✅ Registry stays on the generic tools;
  Read filter/Write schema/Dedicated tool only move to ✅ if an object
  earns a dedicated tool later (see README "Status").

**Promotion criteria (NETBOX-109): not decided yet.** Once
`get_resource_schema` (NETBOX-99) sees real usage, revisit this against a
starting grid — composed semantics, real usage at Distriq, observed error
frequency, sensitivity/scope. It's possible `get_resource_schema` +
`write_resource` end up covering most of the remaining registry well
enough that a dedicated tool becomes the exception rather than the norm.

## DCIM

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| Site | `dcim/sites/` | ✅ | ✅ | ⬜ | ✅ |
| Region | `dcim/regions/` | ✅ | ⬜ | ⬜ | ⬜ |
| Site group | `dcim/site-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Location | `dcim/locations/` | ✅ | ⬜ | ⬜ | ⬜ |
| Rack | `dcim/racks/` | ✅ | ⬜ | ⬜ | ⬜ |
| Rack role | `dcim/rack-roles/` | ✅ | ⬜ | ⬜ | ⬜ |
| Rack reservation | `dcim/rack-reservations/` | ✅ | ⬜ | ⬜ | ⬜ |
| Rack type | `dcim/rack-types/` | ✅ | ⬜ | ⬜ | ⬜ |
| Manufacturer | `dcim/manufacturers/` | ✅ | ⬜ | ⬜ | ⬜ |
| Device type | `dcim/device-types/` | ✅ | ⬜ | ⬜ | ⬜ |
| Module type | `dcim/module-types/` | ✅ | ⬜ | ⬜ | ⬜ |
| Device role | `dcim/device-roles/` | ✅ | ⬜ | ⬜ | ⬜ |
| Platform | `dcim/platforms/` | ✅ | ⬜ | ⬜ | ⬜ |
| Device | `dcim/devices/` | ✅ | ✅ | ✅ | ✅ |
| Module | `dcim/modules/` | ✅ | ⬜ | ⬜ | ⬜ |
| Virtual chassis | `dcim/virtual-chassis/` | ✅ | ⬜ | ⬜ | ⬜ |
| Virtual device context | `dcim/virtual-device-contexts/` | ✅ | ⬜ | ⬜ | ⬜ |
| Device bay | `dcim/device-bays/` | ✅ | ⬜ | ⬜ | ⬜ |
| Module bay | `dcim/module-bays/` | ✅ | ⬜ | ⬜ | ⬜ |
| Inventory item | `dcim/inventory-items/` | ✅ | ⬜ | ⬜ | ⬜ |
| Inventory item role | `dcim/inventory-item-roles/` | ✅ | ⬜ | ⬜ | ⬜ |
| Interface | `dcim/interfaces/` | ✅ | ✅ | ✅ | ✅ |
| MAC address | `dcim/mac-addresses/` | ✅ | ⬜ | ⬜ | ⬜ |
| Console port | `dcim/console-ports/` | ✅ | ⬜ | ⬜ | ⬜ |
| Console server port | `dcim/console-server-ports/` | ✅ | ⬜ | ⬜ | ⬜ |
| Power port | `dcim/power-ports/` | ✅ | ⬜ | ⬜ | ⬜ |
| Power outlet | `dcim/power-outlets/` | ✅ | ⬜ | ⬜ | ⬜ |
| Power panel | `dcim/power-panels/` | ✅ | ⬜ | ⬜ | ⬜ |
| Power feed | `dcim/power-feeds/` | ✅ | ⬜ | ⬜ | ⬜ |
| Front port | `dcim/front-ports/` | ✅ | ⬜ | ⬜ | ⬜ |
| Rear port | `dcim/rear-ports/` | ✅ | ⬜ | ⬜ | ⬜ |
| Cable | `dcim/cables/` | ✅ | ⬜ | ⬜ | ⬜ |
| Device/module/template bays & port templates | `dcim/*-templates/` | ⬜ | ⬜ | ⬜ | ⬜ |

## IPAM

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| VRF | `ipam/vrfs/` | ✅ | ⬜ | ⬜ | ⬜ |
| Route target | `ipam/route-targets/` | ✅ | ⬜ | ⬜ | ⬜ |
| RIR | `ipam/rirs/` | ✅ | ⬜ | ⬜ | ⬜ |
| Aggregate | `ipam/aggregates/` | ✅ | ⬜ | ⬜ | ⬜ |
| IPAM role | `ipam/roles/` | ✅ | ⬜ | ⬜ | ⬜ |
| Prefix | `ipam/prefixes/` | ✅ | ⬜ | ⬜ | ⬜ |
| IP range | `ipam/ip-ranges/` | ✅ | ⬜ | ⬜ | ⬜ |
| IP address | `ipam/ip-addresses/` | ✅ | ✅ | ✅ | ✅ |
| VLAN | `ipam/vlans/` | ✅ | ✅ | ⬜ | ✅ |
| VLAN group | `ipam/vlan-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| ASN | `ipam/asns/` | ✅ | ⬜ | ⬜ | ⬜ |
| ASN range | `ipam/asn-ranges/` | ✅ | ⬜ | ⬜ | ⬜ |
| FHRP group | `ipam/fhrp-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| FHRP group assignment | `ipam/fhrp-group-assignments/` | ✅ | ⬜ | ⬜ | ⬜ |
| Service | `ipam/services/` | ✅ | ⬜ | ⬜ | ⬜ |
| Service template | `ipam/service-templates/` | ✅ | ⬜ | ⬜ | ⬜ |

## Virtualization

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| Cluster type | `virtualization/cluster-types/` | ✅ | ⬜ | ⬜ | ⬜ |
| Cluster group | `virtualization/cluster-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Cluster | `virtualization/clusters/` | ✅ | ⬜ | ⬜ | ⬜ |
| Virtual machine | `virtualization/virtual-machines/` | ✅ | ⬜ | ⬜ | ⬜ |
| VM interface | `virtualization/interfaces/` | ✅ | ⬜ | ⬜ | ⬜ |
| Virtual disk | `virtualization/virtual-disks/` | ✅ | ⬜ | ⬜ | ⬜ |

## Circuits

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| Provider | `circuits/providers/` | ✅ | ⬜ | ⬜ | ⬜ |
| Provider account | `circuits/provider-accounts/` | ✅ | ⬜ | ⬜ | ⬜ |
| Provider network | `circuits/provider-networks/` | ✅ | ⬜ | ⬜ | ⬜ |
| Circuit type | `circuits/circuit-types/` | ✅ | ⬜ | ⬜ | ⬜ |
| Circuit | `circuits/circuits/` | ✅ | ⬜ | ⬜ | ⬜ |
| Circuit termination | `circuits/circuit-terminations/` | ✅ | ⬜ | ⬜ | ⬜ |
| Circuit group | `circuits/circuit-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Circuit group assignment | `circuits/circuit-group-assignments/` | ✅ | ⬜ | ⬜ | ⬜ |

## Tenancy

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| Tenant | `tenancy/tenants/` | ✅ | ⬜ | ⬜ | ⬜ |
| Tenant group | `tenancy/tenant-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Contact | `tenancy/contacts/` | ✅ | ⬜ | ⬜ | ⬜ |
| Contact group | `tenancy/contact-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Contact role | `tenancy/contact-roles/` | ✅ | ⬜ | ⬜ | ⬜ |
| Contact assignment | `tenancy/contact-assignments/` | ✅ | ⬜ | ⬜ | ⬜ |

## Wireless

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| Wireless LAN | `wireless/wireless-lans/` | ✅ | ⬜ | ⬜ | ⬜ |
| Wireless LAN group | `wireless/wireless-lan-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Wireless link | `wireless/wireless-links/` | ✅ | ⬜ | ⬜ | ⬜ |

## VPN

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| Tunnel | `vpn/tunnels/` | ✅ | ⬜ | ⬜ | ⬜ |
| Tunnel group | `vpn/tunnel-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Tunnel termination | `vpn/tunnel-terminations/` | ✅ | ⬜ | ⬜ | ⬜ |
| IKE policy / proposal | `vpn/ike-policies/`, `vpn/ike-proposals/` | ✅ | ⬜ | ⬜ | ⬜ |
| IPSec policy / profile / proposal | `vpn/ipsec-*/` | ✅ | ⬜ | ⬜ | ⬜ |
| L2VPN | `vpn/l2vpns/` | ✅ | ⬜ | ⬜ | ⬜ |
| L2VPN termination | `vpn/l2vpn-terminations/` | ✅ | ⬜ | ⬜ | ⬜ |

## Extras

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| Tag | `extras/tags/` | ✅ | ⬜ | ⬜ | ⬜ |
| Custom field | `extras/custom-fields/` | ✅ | ⬜ | ⬜ | ⬜ |
| Custom field choice set | `extras/custom-field-choice-sets/` | ✅ | ⬜ | ⬜ | ⬜ |
| Custom link | `extras/custom-links/` | ✅ | ⬜ | ⬜ | ⬜ |
| Config context | `extras/config-contexts/` | ✅ | ⬜ | ⬜ | ⬜ |
| Config template | `extras/config-templates/` | ✅ | ⬜ | ⬜ | ⬜ |
| Export template | `extras/export-templates/` | ✅ | ⬜ | ⬜ | ⬜ |
| Saved filter | `extras/saved-filters/` | ✅ | ⬜ | ⬜ | ⬜ |
| Webhook | `extras/webhooks/` | ✅ | ⬜ | ⬜ | ⬜ |
| Event rule | `extras/event-rules/` | ✅ | ⬜ | ⬜ | ⬜ |
| Notification group | `extras/notification-groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Journal entry | `extras/journal-entries/` | ✅ | ⬜ | ⬜ | ⬜ |
| Image attachment | `extras/image-attachments/` | ✅ | ⬜ | ⬜ | ⬜ |
| Bookmark | `extras/bookmarks/` | ✅ | ⬜ | ⬜ | ⬜ |
| Script | `extras/scripts/` | ✅ | ⬜ | ⬜ | ⬜ |

## Users / core

| Object | REST endpoint | Registry | Read filter | Write schema | Dedicated tool |
|---|---|---|---|---|---|
| User | `users/users/` | ✅ | ⬜ | ⬜ | ⬜ |
| Group | `users/groups/` | ✅ | ⬜ | ⬜ | ⬜ |
| Permission | `users/permissions/` | ✅ | ⬜ | ⬜ | ⬜ |
| Token | `users/tokens/` | ✅ | ⬜ | ⬜ | ⬜ |
| Data source | `core/data-sources/` | ✅ | ⬜ | ⬜ | ⬜ |
| Data file | `core/data-files/` | ✅ | ⬜ | ⬜ | ⬜ |
| Job | `core/jobs/` | ✅ | ⬜ | ⬜ | ⬜ |

## Handled outside the registry

`netbox_branching` branches (`plugins/branching/branches/`) are not, and
won't be, exposed as a generic registry resource: they're created and
polled through dedicated helpers in `client/branches.py`
(`create_branch`, `get_branch`, `list_branches`, `wait_until_ready`), and
deliberately have no `merge()`/`sync()`/`revert()`/`archive()` — those stay
a human action in the NetBox UI. See README "Approach" for the rationale.
Branch creation and listing are exposed as MCP tools (`create_branch`,
`list_branches` in `tools/write.py`) — merge is not, for the same reason.

## Updating this file

When a resource is added to `client/registry.py`, flip its Registry cell
to ✅ in the same PR — it's immediately usable via the generic tools, no
further work required. Only flip Read filter/Write schema/Dedicated tool
if that object graduates to a dedicated tool (see README "Status" for when
that's warranted).
