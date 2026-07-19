"""Integration tests for tools/read.py, against a real NetBox instance.

Requires NETBOX_URL / NETBOX_API_TOKEN pointing to a running NetBox instance
with the svc-netbox-mcp service account provisioned (see
scripts/create_service_account.py) — same prerequisites as
test_rest_integration.py.

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
    assert [s["slug"] for s in matches] == [slug]

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

    assert [s["slug"] for s in active_matches] == [slug]
    assert retired_matches == []


def test_get_site_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_site(999_999_999)


def test_list_devices_smoke():
    assert isinstance(read.list_devices(), list)


def test_get_device_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_device(999_999_999)


def test_list_interfaces_with_filter_matching_nothing_is_empty():
    bogus_name = f"netbox-mcp-test-{uuid.uuid4().hex}"
    assert read.list_interfaces(InterfaceFilter(name=bogus_name)) == []


def test_get_interface_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_interface(999_999_999)


def test_list_ip_addresses_smoke():
    assert isinstance(read.list_ip_addresses(), list)


def test_get_ip_address_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_ip_address(999_999_999)


def test_list_vlans_smoke():
    assert isinstance(read.list_vlans(), list)


def test_get_vlan_missing_raises_not_found():
    with pytest.raises(NetBoxNotFoundError):
        read.get_vlan(999_999_999)
