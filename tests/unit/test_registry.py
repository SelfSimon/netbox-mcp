import pytest

from client.registry import get_model_spec, list_resources


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
