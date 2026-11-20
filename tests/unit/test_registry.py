import pytest

from client.registry import get_model_spec, iter_model_specs, list_resources


def test_list_resources_is_sorted_and_non_empty():
    resources = list_resources()

    assert resources == sorted(resources)
    assert "device" in resources
    assert "ip_address" in resources


def test_get_model_spec_returns_expected_fields():
    spec = get_model_spec("device")

    assert spec.rest_path == "dcim/devices/"


def test_get_model_spec_raises_key_error_for_unknown_resource():
    with pytest.raises(KeyError):
        get_model_spec("not-a-real-resource")


COMPONENT_TEMPLATES = {
    "console_port_template": "dcim/console-port-templates/",
    "console_server_port_template": "dcim/console-server-port-templates/",
    "device_bay_template": "dcim/device-bay-templates/",
    "front_port_template": "dcim/front-port-templates/",
    "interface_template": "dcim/interface-templates/",
    "inventory_item_template": "dcim/inventory-item-templates/",
    "module_bay_template": "dcim/module-bay-templates/",
    "power_outlet_template": "dcim/power-outlet-templates/",
    "power_port_template": "dcim/power-port-templates/",
    "rear_port_template": "dcim/rear-port-templates/",
}


@pytest.mark.parametrize(("resource", "rest_path"), COMPONENT_TEMPLATES.items())
def test_every_component_template_is_registered(resource, rest_path):
    assert get_model_spec(resource).rest_path == rest_path


@pytest.mark.parametrize(
    ("resource", "rest_path"),
    [("owner", "users/owners/"), ("owner_group", "users/owner-groups/")],
)
def test_ownership_resources_are_registered(resource, rest_path):
    assert get_model_spec(resource).rest_path == rest_path


# netbox_branching ignores X-NetBox-Branch for these (no change logging, or
# exempted by the plugin): a write would land directly on main (NETBOX-142).
NOT_BRANCHABLE = {
    "bookmark",
    "custom_field",
    "custom_field_choice_set",
    "custom_link",
    "data_file",
    "data_source",
    "event_rule",
    "export_template",
    "group",
    "job",
    "notification_group",
    "owner",
    "owner_group",
    "permission",
    "saved_filter",
    "script",
    "token",
    "user",
    "webhook",
}


def test_only_the_resources_netbox_branching_ignores_are_not_branchable():
    not_branchable = {name for name, spec in iter_model_specs() if not spec.branchable}

    assert not_branchable == NOT_BRANCHABLE


def test_resources_are_branchable_by_default():
    assert get_model_spec("device").branchable is True
    assert get_model_spec("tag").branchable is True
