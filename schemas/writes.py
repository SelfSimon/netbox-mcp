"""Pydantic write-payload schemas for the NetBox write tools.

Create schemas require the fields NetBox itself requires for that
endpoint; Update schemas make every field optional, matching
client/rest.py's `patch()` (partial update). NetBox is still the final
authority regardless of what passes validation here — invalid values raise
NetBoxValidationError from the client, not from these schemas.

Currently covers device create/update (including rack mounting, platform,
owner, primary IPs, tags and custom fields), interface create/update
(including PoE, 802.1Q mode and VLANs, LAG, parent, VRF, tags and custom
fields), and IP address assignment — the first slice of write tools.
`custom_fields` is a free dict (NETBOX-141): which custom fields exist is
NetBox data, not code, so NetBox validates them. VLAN, site, and
every other NetBox resource get a write schema the same way as their
write tool is added; the goal is full read/write coverage of the NetBox
object model, with NetBox's own per-user permissions (not this schema
layer) as the actual access boundary.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .choices import (
    DeviceAirflow,
    DeviceFace,
    DeviceStatus,
    InterfaceDuplex,
    InterfaceMode,
    InterfacePoEMode,
    InterfacePoEType,
    IPAddressStatus,
)


class _PayloadBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_payload(self) -> dict[str, Any]:
        # mode="json": enum members become their plain string value.
        return self.model_dump(exclude_none=True, mode="json")


class TagRef(_PayloadBase):
    """A tag, referenced by `name` and/or `slug` (the tag must exist)."""

    name: str | None = None
    slug: str | None = None

    @model_validator(mode="after")
    def _needs_name_or_slug(self) -> TagRef:
        if self.name is None and self.slug is None:
            raise ValueError("a tag needs a `name` or a `slug`")
        return self


_TAGS_DESCRIPTION = (
    'Tags as objects, e.g. [{"name": "core"}] or [{"slug": "core"}]. '
    "Replaces every tag on the object; the tags must already exist."
)

_CUSTOM_FIELDS_DESCRIPTION = (
    'Custom field values by field name, e.g. {"circuit_ref": "X-42"}. '
    "An update changes only the custom fields named here; null clears one. "
    "get_resource_schema() lists the custom fields defined for this object "
    "type with their types; NetBox validates the values."
)


def _custom_fields() -> Any:
    return Field(None, description=_CUSTOM_FIELDS_DESCRIPTION)


class _DeviceFields(_PayloadBase):
    """Optional device fields shared by DeviceCreate and DeviceUpdate."""

    serial: str | None = None
    asset_tag: str | None = None
    tenant: int | None = None
    location: int | None = None
    rack: int | None = None
    position: float | None = Field(
        None,
        ge=0.5,
        multiple_of=0.5,
        description=(
            "Lowest rack unit the device occupies (half units allowed, "
            "e.g. 10.5). Needs `rack` and `face`."
        ),
    )
    face: DeviceFace | None = Field(
        None, description="Rack face the device is mounted on."
    )
    airflow: DeviceAirflow | None = None
    platform: int | None = None
    cluster: int | None = None
    owner: int | None = Field(
        None, description="Owner id (look it up with get_resource('owner'))."
    )
    primary_ip4: int | None = Field(
        None,
        description="IP address id; the IP must be assigned to this device.",
    )
    primary_ip6: int | None = Field(
        None,
        description="IP address id; the IP must be assigned to this device.",
    )
    description: str | None = None
    comments: str | None = None
    tags: list[TagRef] | None = Field(None, description=_TAGS_DESCRIPTION)
    custom_fields: dict[str, Any] | None = _custom_fields()


class DeviceCreate(_DeviceFields):
    name: str
    device_type: int
    role: int
    site: int
    status: DeviceStatus = DeviceStatus.ACTIVE


class DeviceUpdate(_DeviceFields):
    name: str | None = None
    device_type: int | None = None
    role: int | None = None
    site: int | None = None
    status: DeviceStatus | None = None


class _InterfaceFields(_PayloadBase):
    """Optional interface fields shared by InterfaceCreate and
    InterfaceUpdate."""

    label: str | None = None
    mtu: int | None = None
    mac_address: str | None = None
    speed: int | None = Field(None, ge=0, description="Speed in Kbps.")
    duplex: InterfaceDuplex | None = None
    mgmt_only: bool | None = None
    mark_connected: bool | None = Field(
        None, description="Treat the interface as connected without a cable."
    )
    poe_mode: InterfacePoEMode | None = None
    poe_type: InterfacePoEType | None = None
    mode: InterfaceMode | None = Field(
        None, description="802.1Q mode; needed before setting VLANs."
    )
    untagged_vlan: int | None = Field(None, description="VLAN id.")
    tagged_vlans: list[int] | None = Field(
        None, description="VLAN ids; needs `mode` = tagged."
    )
    lag: int | None = Field(
        None, description="Id of the LAG interface this one is a member of."
    )
    parent: int | None = Field(
        None, description="Id of the parent interface (sub-interfaces)."
    )
    vrf: int | None = None
    description: str | None = None
    tags: list[TagRef] | None = Field(None, description=_TAGS_DESCRIPTION)
    custom_fields: dict[str, Any] | None = _custom_fields()


class InterfaceCreate(_InterfaceFields):
    device: int
    name: str
    type: str
    enabled: bool = True


class InterfaceUpdate(_InterfaceFields):
    name: str | None = None
    type: str | None = None
    enabled: bool | None = None


class IPAddressAssign(_PayloadBase):
    """Create an IP address already assigned to an interface — the write
    tool's actual workflow ("IP assignment tool"), as opposed to creating a
    bare, unassigned IP address.
    """

    address: str
    assigned_object_id: int
    assigned_object_type: str = "dcim.interface"
    status: IPAddressStatus = IPAddressStatus.ACTIVE
    dns_name: str | None = None
    description: str | None = None
    custom_fields: dict[str, Any] | None = _custom_fields()
