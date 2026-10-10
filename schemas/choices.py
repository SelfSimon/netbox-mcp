"""NetBox ChoiceSet enumerations relevant to the resources exposed by this
client (site, device, ip_address, vlan), copied from NetBox 4.6's own
`dcim.choices` / `ipam.choices` so tool schemas expose valid values to the
LLM without a live NetBox round trip.

Copied, not imported: this project has no dependency on NetBox's source
tree (see client/rest.py's REST-only design). Values must be kept in sync
by hand if NetBox adds/renames choices in a future version — NetBox itself
remains the final authority and rejects anything invalid via its own
server-side validation (NetBoxValidationError), regardless of what these
enums allow.

Interface `type` is deliberately not copied here: NetBox ships several
hundred values for it, they change often, and NetBox already validates the
field server-side — duplicating the list would only go stale.
"""

from __future__ import annotations

from enum import Enum


class SiteStatus(str, Enum):
    PLANNED = "planned"
    STAGING = "staging"
    ACTIVE = "active"
    DECOMMISSIONING = "decommissioning"
    RETIRED = "retired"


class DeviceStatus(str, Enum):
    OFFLINE = "offline"
    ACTIVE = "active"
    PLANNED = "planned"
    STAGED = "staged"
    FAILED = "failed"
    INVENTORY = "inventory"
    DECOMMISSIONING = "decommissioning"


class IPAddressStatus(str, Enum):
    ACTIVE = "active"
    RESERVED = "reserved"
    DEPRECATED = "deprecated"
    DHCP = "dhcp"
    SLAAC = "slaac"


class VLANStatus(str, Enum):
    ACTIVE = "active"
    RESERVED = "reserved"
    DEPRECATED = "deprecated"
