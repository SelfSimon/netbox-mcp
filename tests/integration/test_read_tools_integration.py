"""Integration tests for tools/read.py, against a real NetBox instance.

Requires NETBOX_URL / NETBOX_TEST_TOKEN (see conftest.py) — same
prerequisites as test_rest_integration.py.

Test objects created here (sites) accumulate in the target instance; clean
them up periodically by hand, same as test_rest_integration.py.
"""

import uuid

import pytest

from client.exceptions import NetBoxNotFoundError
from client.rest import NetBoxRestClient
from schemas.choices import SiteStatus
from schemas.filters import InterfaceFilter, SiteFilter
from tools import read

pytestmark = pytest.mark.integration


def test_list_sites_and_get_site_round_trip():
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    with NetBoxRestClient() as bootstrap_client:
        created = bootstrap_client.create("site", {"name": slug, "slug": slug})

    matches = read.list_sites(SiteFilter(slug=slug))
    assert [s["slug"] for s in matches["results"]] == [slug]
    assert matches["count"] == 1
    assert matches["truncated"] is False

    fetched = read.get_site(created["id"])
    assert fetched["slug"] == slug


def test_status_filter_is_honored_by_netbox_not_silently_ignored():
    """Regression test for the to_params() enum-serialization bug: before
    the fix, a status filter was sent as the literal string
    "SiteStatus.ACTIVE" instead of "active". NetBox doesn't recognize
    that value and silently ignores the filter, so querying for
    status=retired would still (wrongly) return a freshly created
    (active) site. Asserting it does NOT catches that regression.
    """
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    with NetBoxRestClient() as bootstrap_client:
        bootstrap_client.create("site", {"name": slug, "slug": slug})

    active_matches = read.list_sites(SiteFilter(slug=slug, status=SiteStatus.ACTIVE))
    retired_matches = read.list_sites(SiteFilter(slug=slug, status=SiteStatus.RETIRED))

    assert [s["slug"] for s in active_matches["results"]] == [slug]
    assert retired_matches["results"] == []


def test_brief_and_fields_are_honored_by_netbox():
    """NETBOX-114: both are plain query params, so NetBox silently ignores
    them if the deployed version doesn't support them — assert on the keys
    actually returned."""
    slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
    with NetBoxRestClient() as bootstrap_client:
        created = bootstrap_client.create("site", {"name": slug, "slug": slug})

    full = read.get_site(created["id"])
    brief = read.get_site(created["id"], brief=True)
    selected = read.get_site(created["id"], fields=["id", "slug"])
    listed = read.list_sites(SiteFilter(slug=slug, fields=["id", "slug"]))
    listed_brief = read.list_sites(SiteFilter(slug=slug, brief=True))

    assert "custom_fields" in full
    assert "custom_fields" not in brief
    assert set(brief) < set(full)
    assert selected == {"id": created["id"], "slug": slug}
    assert listed["results"] == [{"id": created["id"], "slug": slug}]
    assert "custom_fields" not in listed_brief["results"][0]


def test_list_sites_is_bounded_and_reports_the_total():
    """NETBOX-113: `limit=1` returns one site, with the real total."""
    for _ in range(2):
        slug = f"netbox-mcp-test-{uuid.uuid4().hex[:8]}"
        with NetBoxRestClient() as bootstrap_client:
            bootstrap_client.create("site", {"name": slug, "slug": slug})

    page = read.list_sites(SiteFilter(limit=1))

    assert page["returned"] == 1
    assert page["count"] >= 2
    assert page["truncated"] is True
    assert page["next_offset"] == 1


def test_get_site_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_site(999_999_999)


def test_list_devices_smoke():
    page = read.list_devices()
    assert page["returned"] == len(page["results"]) <= 50
    assert page["count"] >= page["returned"]


def test_get_device_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_device(999_999_999)


def test_list_interfaces_with_filter_matching_nothing_is_empty():
    bogus_name = f"netbox-mcp-test-{uuid.uuid4().hex}"
    page = read.list_interfaces(InterfaceFilter(name=bogus_name))
    assert page["results"] == []
    assert page["count"] == 0
    assert page["truncated"] is False


def test_get_interface_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_interface(999_999_999)


def test_list_ip_addresses_smoke():
    page = read.list_ip_addresses()
    assert page["returned"] == len(page["results"]) <= 50
    assert page["count"] >= page["returned"]


def test_get_ip_address_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_ip_address(999_999_999)


def test_list_vlans_smoke():
    page = read.list_vlans()
    assert page["returned"] == len(page["results"]) <= 50
    assert page["count"] >= page["returned"]


def test_get_vlan_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_vlan(999_999_999)
