"""Pydantic filter schemas for the NetBox read tools.

Each field maps 1:1 to a NetBox REST API filter query parameter — no
translation happens here or in client/rest.py (`list()` forwards filters
as-is to NetBox). `to_params()` drops unset fields so only filters the
caller actually supplied are sent, matching NetBox's own "unfiltered means
all" default. Currently covers site, device, interface, ip_address, and
vlan — the first slice of read tools. Every other NetBox resource gets a
filter schema the same way as its read tool is added, working toward full
object coverage (see `client/registry.py`).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .choices import DeviceStatus, IPAddressStatus, SiteStatus, VLANStatus


class _FilterBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_params(self) -> dict[str, Any]:
        """Dump to query-param-ready primitives.

        `mode="json"` matters here: status fields are `str, Enum` members,
        and a plain (Python-mode) dump leaves the enum member itself in the
        dict. httpx's query-param encoder calls `str()` on values, and
        `str()` on a mixed-in `str, Enum` member returns "ClassName.MEMBER"
        (e.g. "DeviceStatus.ACTIVE"), not its string value — silently
        sending a filter NetBox doesn't recognize. `mode="json"` dumps
        enums to their plain value instead.
        """
        return self.model_dump(exclude_none=True, mode="json")


class SiteFilter(_FilterBase):
    q: str | None = None
    name: str | None = None
    slug: str | None = None
    status: SiteStatus | None = None
    region_id: int | None = None
    tenant_id: int | None = None


class DeviceFilter(_FilterBase):
    q: str | None = None
    name: str | None = None
    site_id: int | None = None
    role_id: int | None = None
    device_type_id: int | None = None
    manufacturer_id: int | None = None
    status: DeviceStatus | None = None
    serial: str | None = None
    tenant_id: int | None = None


class InterfaceFilter(_FilterBase):
    q: str | None = None
    device_id: int | None = None
    name: str | None = None
    type: str | None = None
    enabled: bool | None = None
    mac_address: str | None = None


class IPAddressFilter(_FilterBase):
    q: str | None = None
    address: str | None = None
    status: IPAddressStatus | None = None
    vrf_id: int | None = None
    device_id: int | None = None
    interface_id: int | None = None
    tenant_id: int | None = None


class VLANFilter(_FilterBase):
    q: str | None = None
    vid: int | None = None
    name: str | None = None
    site_id: int | None = None
    group_id: int | None = None
    status: VLANStatus | None = None
    tenant_id: int | None = None
