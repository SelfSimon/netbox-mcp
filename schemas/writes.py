"""Pydantic write-payload schemas for the NetBox write tools.

Create schemas require the fields NetBox itself requires for that
endpoint; Update schemas make every field optional, matching
client/rest.py's `patch()` (partial update). NetBox is still the final
authority regardless of what passes validation here — invalid values raise
NetBoxValidationError from the client, not from these schemas.

Scope covers device create/update, interface create/update, and IP
address assignment. VLAN and site have no write tool planned yet, so no
write schema for them here (see filters.py for their read-side schemas).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .choices import DeviceStatus, IPAddressStatus


class _PayloadBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class DeviceCreate(_PayloadBase):
    name: str
    device_type: int
    role: int
    site: int
    status: DeviceStatus = DeviceStatus.ACTIVE
    serial: str | None = None
    asset_tag: str | None = None
    tenant: int | None = None
    location: int | None = None
    rack: int | None = None
    comments: str | None = None


class DeviceUpdate(_PayloadBase):
    name: str | None = None
    device_type: int | None = None
    role: int | None = None
    site: int | None = None
    status: DeviceStatus | None = None
    serial: str | None = None
    asset_tag: str | None = None
    tenant: int | None = None
    location: int | None = None
    rack: int | None = None
    comments: str | None = None


class InterfaceCreate(_PayloadBase):
    device: int
    name: str
    type: str
    enabled: bool = True
    mtu: int | None = None
    mac_address: str | None = None
    description: str | None = None


class InterfaceUpdate(_PayloadBase):
    name: str | None = None
    type: str | None = None
    enabled: bool | None = None
    mtu: int | None = None
    mac_address: str | None = None
    description: str | None = None


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
