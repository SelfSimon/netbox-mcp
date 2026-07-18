import pytest
from pydantic import ValidationError

from schemas.choices import DeviceStatus
from schemas.filters import DeviceFilter, SiteFilter


def test_filter_to_params_drops_unset_fields():
    f = DeviceFilter(name="sw01", status=DeviceStatus.ACTIVE)

    assert f.to_params() == {"name": "sw01", "status": "active"}


def test_filter_to_params_empty_when_nothing_set():
    assert SiteFilter().to_params() == {}


def test_filter_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DeviceFilter(not_a_real_filter="x")
