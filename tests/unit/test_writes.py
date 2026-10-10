import pytest
from pydantic import ValidationError

from schemas.writes import DeviceCreate, DeviceUpdate, InterfaceCreate, IPAddressAssign


def test_device_create_requires_core_fields():
    with pytest.raises(ValidationError):
        DeviceCreate(name="sw01")


def test_device_create_applies_default_status():
    d = DeviceCreate(name="sw01", device_type=1, role=2, site=3)

    assert d.to_payload()["status"] == "active"


def test_device_update_allows_partial_payload():
    u = DeviceUpdate(serial="ABC123")

    assert u.to_payload() == {"serial": "ABC123"}


def test_interface_create_requires_device_name_type():
    with pytest.raises(ValidationError):
        InterfaceCreate(name="eth0")


def test_ip_address_assign_defaults_to_interface_type():
    ip = IPAddressAssign(address="10.0.0.1/32", assigned_object_id=5)
    payload = ip.to_payload()

    assert payload["assigned_object_type"] == "dcim.interface"
    assert payload["status"] == "active"
