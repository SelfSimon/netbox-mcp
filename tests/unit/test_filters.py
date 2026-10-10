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


def test_filter_to_params_sends_brief_only_when_set():
    assert "brief" not in SiteFilter().to_params()
    assert SiteFilter(brief=True).to_params()["brief"] is True


def test_filter_to_params_joins_fields_with_commas():
    f = DeviceFilter(fields=["id", "name", "primary_ip4"])

    assert f.to_params()["fields"] == "id,name,primary_ip4"


@pytest.mark.parametrize("limit", [0, -1, 1001])
def test_filter_rejects_limit_outside_the_allowed_range(limit):
    with pytest.raises(ValidationError):
        SiteFilter(limit=limit)


def test_filter_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DeviceFilter(not_a_real_filter="x")
