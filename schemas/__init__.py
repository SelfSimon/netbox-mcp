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
    "choices",
    "filters",
    "writes",
    "DeviceStatus",
    "IPAddressStatus",
    "SiteStatus",
    "VLANStatus",
    "DeviceFilter",
    "InterfaceFilter",
    "IPAddressFilter",
    "SiteFilter",
    "VLANFilter",
    "DeviceCreate",
    "DeviceUpdate",
    "InterfaceCreate",
    "InterfaceUpdate",
    "IPAddressAssign",
]
