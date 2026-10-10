"""Pydantic filter schemas for the NetBox read tools.

Each field maps 1:1 to a NetBox REST API filter query parameter — no
translation happens here or in client/rest.py (`list()` forwards filters
as-is to NetBox). `to_params()` drops unset fields so only filters the
caller actually supplied are sent, matching NetBox's own "unfiltered means
all" default. Currently covers site, device, interface, ip_address, and
vlan — the first slice of read tools. Every other NetBox resource gets a
filter schema the same way as its read tool is added, working toward full
object coverage (see `client/registry.py`).

`_FilterBase` also carries `limit`/`offset`/`ordering` and the field
selection (`brief`/`fields`), shared by every filter below. `limit`
defaults to 50 (rather than unset, like every other field) so a `list_*`
call with no explicit limit still returns a bounded page instead of risking
the 1MB MCP tool-result cap on large NetBox instances (see NETBOX-96), and
it cannot exceed `MAX_LIST_LIMIT` (NETBOX-113): page with `offset` instead.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from client.rest import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT

from .choices import DeviceStatus, IPAddressStatus, SiteStatus, VLANStatus


class _FilterBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int | None = Field(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT)
    offset: int | None = Field(None, ge=0)
    ordering: str | None = None
    brief: bool = Field(
        False,
        description=(
            "Return NetBox's minimal representation of each object (id, url, "
            "display, name and a few key fields). Much smaller, but without "
            "custom fields, tags or related objects — not a substitute for a "
            "full read."
        ),
    )
    fields: list[str] | None = Field(
        None,
        description=(
            'Return only these fields of each object, e.g. ["id", "name", '
            '"primary_ip4"]. Prefer this over `brief` when you know which '
            "fields you need."
        ),
    )

    def to_params(self) -> dict[str, Any]:
        """Dump to query-param-ready primitives.

        `mode="json"` matters here: status fields are `str, Enum` members,
        and a plain (Python-mode) dump leaves the enum member itself in the
        dict. httpx's query-param encoder calls `str()` on values, and
        `str()` on a mixed-in `str, Enum` member returns "ClassName.MEMBER"
        (e.g. "DeviceStatus.ACTIVE"), not its string value — silently
        sending a filter NetBox doesn't recognize. `mode="json"` dumps
        enums to their plain value instead.

        `brief` is only sent when set, and `fields` as the comma-separated
        list NetBox expects.
        """
        params = self.model_dump(exclude_none=True, mode="json")
        if not params["brief"]:
            del params["brief"]
        if "fields" in params:
            params["fields"] = ",".join(params["fields"])
        return params


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
