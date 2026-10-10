"""Pydantic schemas for validating tool inputs, and NetBox ChoiceSet
enumerations copied from NetBox 4.6 (see choices.py).
"""

from . import choices, filters, writes
from .choices import DeviceStatus, IPAddressStatus, SiteStatus, VLANStatus
from .filters import (
    DeviceFilter,
    InterfaceFilter,
    IPAddressFilter,
    SiteFilter,
    VLANFilter,
)
from .writes import (
    DeviceCreate,
    DeviceUpdate,
    InterfaceCreate,
    InterfaceUpdate,
    IPAddressAssign,
)

__all__ = [
    "DeviceCreate",
    "DeviceFilter",
    "DeviceStatus",
    "DeviceUpdate",
    "IPAddressAssign",
    "IPAddressFilter",
    "IPAddressStatus",
    "InterfaceCreate",
    "InterfaceFilter",
    "InterfaceUpdate",
    "SiteFilter",
    "SiteStatus",
    "VLANFilter",
    "VLANStatus",
    "choices",
    "filters",
    "writes",
]
