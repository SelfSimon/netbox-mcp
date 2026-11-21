"""NetBox ChoiceSet enumerations relevant to the resources exposed by this
client (site, device, interface, ip_address, vlan), copied from NetBox 4.6's own
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


class DeviceFace(str, Enum):
    FRONT = "front"
    REAR = "rear"


class DeviceAirflow(str, Enum):
    FRONT_TO_REAR = "front-to-rear"
    REAR_TO_FRONT = "rear-to-front"
    LEFT_TO_RIGHT = "left-to-right"
    RIGHT_TO_LEFT = "right-to-left"
    SIDE_TO_REAR = "side-to-rear"
    REAR_TO_SIDE = "rear-to-side"
    BOTTOM_TO_TOP = "bottom-to-top"
    TOP_TO_BOTTOM = "top-to-bottom"
    PASSIVE = "passive"
    MIXED = "mixed"


class InterfaceMode(str, Enum):
    ACCESS = "access"
    TAGGED = "tagged"
    TAGGED_ALL = "tagged-all"
    Q_IN_Q = "q-in-q"


class InterfacePoEMode(str, Enum):
    PD = "pd"
    PSE = "pse"


class InterfacePoEType(str, Enum):
    TYPE1_IEEE802_3AF = "type1-ieee802.3af"
    TYPE2_IEEE802_3AT = "type2-ieee802.3at"
    TYPE3_IEEE802_3BT = "type3-ieee802.3bt"
    TYPE4_IEEE802_3BT = "type4-ieee802.3bt"
    PASSIVE_24V_2PAIR = "passive-24v-2pair"
    PASSIVE_24V_4PAIR = "passive-24v-4pair"
    PASSIVE_48V_2PAIR = "passive-48v-2pair"
    PASSIVE_48V_4PAIR = "passive-48v-4pair"


class InterfaceDuplex(str, Enum):
    HALF = "half"
    FULL = "full"
    AUTO = "auto"
