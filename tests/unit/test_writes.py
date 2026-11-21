import pytest
from pydantic import ValidationError

from schemas.writes import (
    DeviceCreate,
    DeviceUpdate,
    InterfaceCreate,
    InterfaceUpdate,
    IPAddressAssign,
)


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


def test_device_create_accepts_rack_mounting_and_relations():
    d = DeviceCreate(
        name="sw01",
        device_type=1,
        role=2,
        site=3,
        rack=4,
        position=42,
        face="front",
        airflow="front-to-rear",
        owner=5,
        platform=6,
        cluster=7,
        description="Core switch",
        tags=[{"name": "nord-quantique"}, {"slug": "core"}],
    )

    payload = d.to_payload()
    assert payload["position"] == 42
    assert payload["face"] == "front"
    assert payload["airflow"] == "front-to-rear"
    assert payload["owner"] == 5
    assert payload["platform"] == 6
    assert payload["cluster"] == 7
    assert payload["tags"] == [{"name": "nord-quantique"}, {"slug": "core"}]


def test_device_position_accepts_half_units_only():
    assert DeviceUpdate(position=10.5).to_payload() == {"position": 10.5}
    with pytest.raises(ValidationError):
        DeviceUpdate(position=10.25)
    with pytest.raises(ValidationError):
        DeviceUpdate(position=0)


def test_device_update_sets_primary_ips():
    u = DeviceUpdate(primary_ip4=10, primary_ip6=11)

    assert u.to_payload() == {"primary_ip4": 10, "primary_ip6": 11}


def test_invalid_face_is_rejected_with_the_allowed_values():
    with pytest.raises(ValidationError) as excinfo:
        DeviceUpdate(face="top")

    message = str(excinfo.value)
    assert "'front'" in message
    assert "'rear'" in message


def test_tag_reference_needs_a_name_or_slug():
    with pytest.raises(ValidationError):
        DeviceUpdate(tags=[{}])
    with pytest.raises(ValidationError):
        DeviceUpdate(tags=[5])


def test_interface_create_accepts_poe_and_management_fields():
    i = InterfaceCreate(
        device=1,
        name="port1",
        type="1000base-t",
        mgmt_only=False,
        poe_mode="pse",
        poe_type="type2-ieee802.3at",
        speed=1_000_000,
        duplex="full",
        label="P1",
        mark_connected=True,
        tags=[{"slug": "poe"}],
    )

    payload = i.to_payload()
    assert payload["poe_mode"] == "pse"
    assert payload["poe_type"] == "type2-ieee802.3at"
    assert payload["speed"] == 1_000_000
    assert payload["duplex"] == "full"
    assert payload["label"] == "P1"
    assert payload["mark_connected"] is True
    assert payload["tags"] == [{"slug": "poe"}]


def test_interface_create_accepts_vlans_lag_parent_and_vrf():
    i = InterfaceCreate(
        device=1,
        name="port2",
        type="1000base-t",
        mode="tagged",
        untagged_vlan=10,
        tagged_vlans=[20, 30],
        lag=40,
        parent=50,
        vrf=60,
    )

    payload = i.to_payload()
    assert payload["mode"] == "tagged"
    assert payload["untagged_vlan"] == 10
    assert payload["tagged_vlans"] == [20, 30]
    assert payload["lag"] == 40
    assert payload["parent"] == 50
    assert payload["vrf"] == 60


def test_interface_update_allows_partial_poe_change():
    assert InterfaceUpdate(poe_mode="pd").to_payload() == {"poe_mode": "pd"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("poe_mode", "poe+"),
        ("poe_type", "802.3at"),
        ("duplex", "1g"),
        ("mode", "trunk"),
    ],
)
def test_interface_rejects_invalid_choices(field, value):
    with pytest.raises(ValidationError):
        InterfaceUpdate(**{field: value})


def test_interface_mgmt_only():
    i = InterfaceCreate(device=1, name="mgmt", type="1000base-t", mgmt_only=True)

    assert i.to_payload()["mgmt_only"] is True
