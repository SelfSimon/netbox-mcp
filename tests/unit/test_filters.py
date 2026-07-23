import pytest
from pydantic import ValidationError

from schemas.choices import DeviceStatus
from schemas.filters import DeviceFilter, SiteFilter


def test_filter_to_params_drops_unset_fields():
    f = DeviceFilter(name="sw01", status=DeviceStatus.ACTIVE, limit=None)

    assert f.to_params() == {"name": "sw01", "status": "active"}


def test_filter_to_params_defaults_to_limit_fifty_when_nothing_set():
    assert SiteFilter().to_params() == {"limit": 50}


def test_filter_to_params_supports_pagination_and_ordering():
    f = SiteFilter(limit=10, offset=20, ordering="-created")

    assert f.to_params() == {"limit": 10, "offset": 20, "ordering": "-created"}


def test_filter_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DeviceFilter(not_a_real_filter="x")
