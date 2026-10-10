import asyncio
import json

import httpx
import pytest
from fastmcp import FastMCP

from client.config import ClientSettings
from client.rest import NetBoxRestClient
from schemas.choices import DeviceStatus
from schemas.filters import DeviceFilter, SiteFilter
from tools import read
from tools.response import ResponseTooLargeError


def make_client(handler) -> NetBoxRestClient:
    settings = ClientSettings(
        netbox_url="http://netbox.local", netbox_api_token="token123"
    )
    client = NetBoxRestClient(settings)
    client._client = httpx.Client(
        base_url="http://netbox.local/api/",
        headers=client._client.headers,
        transport=httpx.MockTransport(handler),
    )
    return client


def test_list_sites_sends_filters_as_query_params(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "active"
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    assert read.list_sites(SiteFilter(status="active")) == {
        "count": 0,
        "returned": 0,
        "offset": 0,
        "truncated": False,
        "next_offset": None,
        "results": [],
    }


def test_list_devices_reports_count_and_truncation(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "count": 300,
                "next": "http://netbox.local/api/dcim/devices/?limit=2&offset=12",
                "previous": None,
                "results": [{"id": 1}, {"id": 2}],
            },
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    result = read.list_devices(DeviceFilter(limit=2, offset=10))

    assert result["count"] == 300
    assert result["returned"] == 2
    assert result["truncated"] is True
    assert result["next_offset"] == 12


def test_list_devices_sends_brief_and_fields(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["brief"] == "true"
        assert request.url.params["fields"] == "id,name"
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    read.list_devices(DeviceFilter(brief=True, fields=["id", "name"]))


def test_list_over_the_size_cap_is_truncated_and_stays_under_it(monkeypatch):
    """NETBOX-116: 50 items is a bounded count, not a bounded size."""
    devices = [{"id": i, "config_context": {"blob": "x" * 1000}} for i in range(50)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"count": 50, "next": None, "previous": None, "results": devices},
        )

    monkeypatch.setenv("MCP_MAX_RESPONSE_BYTES", "10000")
    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    result = read.list_devices()

    assert 0 < result["returned"] < 50
    assert result["results"] == devices[: result["returned"]]
    assert result["count"] == 50
    assert result["truncated"] is True
    assert result["next_offset"] == result["returned"]
    assert "fields" in result["hint"]
    assert len(json.dumps(result).encode()) <= 10000


def test_list_whose_first_object_exceeds_the_cap_returns_none_with_a_hint(
    monkeypatch,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{"id": 1, "config_context": {"blob": "x" * 5000}}],
            },
        )

    monkeypatch.setenv("MCP_MAX_RESPONSE_BYTES", "2000")
    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    result = read.list_devices()

    assert result["results"] == []
    assert result["truncated"] is True
    assert "alone exceeds" in result["hint"]


def test_get_device_over_the_size_cap_raises_an_explicit_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"id": 42, "config_context": {"blob": "x" * 5000}}
        )

    monkeypatch.setenv("MCP_MAX_RESPONSE_BYTES", "2000")
    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    with pytest.raises(ResponseTooLargeError, match="fields"):
        read.get_device(42)


def test_get_device_sends_field_selection(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["fields"] == "id,name"
        return httpx.Response(200, json={"id": 42, "name": "sw01"})

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    assert read.get_device(42, fields=["id", "name"]) == {"id": 42, "name": "sw01"}


def test_list_sites_defaults_to_limit_fifty_when_omitted(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == {"limit": "50"}
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    read.list_sites()


def test_get_site_requests_object_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/dcim/sites/7/"
        return httpx.Response(200, json={"id": 7, "name": "dc1"})

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    assert read.get_site(7) == {"id": 7, "name": "dc1"}


def test_list_devices_sends_filters_as_query_params(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "active"
        assert request.url.params["site_id"] == "3"
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    read.list_devices(DeviceFilter(status=DeviceStatus.ACTIVE, site_id=3))


def test_get_device_requests_object_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/dcim/devices/42/"
        return httpx.Response(200, json={"id": 42, "name": "sw01"})

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    assert read.get_device(42) == {"id": 42, "name": "sw01"}


def test_list_interfaces_requests_interfaces_path(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/dcim/interfaces/"
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    read.list_interfaces()


def test_get_interface_requests_object_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/dcim/interfaces/5/"
        return httpx.Response(200, json={"id": 5, "name": "eth0"})

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    assert read.get_interface(5) == {"id": 5, "name": "eth0"}


def test_list_ip_addresses_requests_ip_addresses_path(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/ipam/ip-addresses/"
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    read.list_ip_addresses()


def test_get_ip_address_requests_object_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/ipam/ip-addresses/9/"
        return httpx.Response(200, json={"id": 9, "address": "10.0.0.1/24"})

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    assert read.get_ip_address(9) == {"id": 9, "address": "10.0.0.1/24"}


def test_list_vlans_requests_vlans_path(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/ipam/vlans/"
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    read.list_vlans()


def test_get_vlan_requests_object_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/ipam/vlans/11/"
        return httpx.Response(200, json={"id": 11, "vid": 100})

    monkeypatch.setattr(read, "_client", lambda: make_client(handler))

    assert read.get_vlan(11) == {"id": 11, "vid": 100}


def test_client_uses_caller_token(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local")
    monkeypatch.setattr("netbox_mcp.auth.get_current_token", lambda: "caller-token")
    monkeypatch.setattr(read, "get_current_token", lambda: "caller-token")

    client = read._client()

    assert client._client.headers["Authorization"] == "Token caller-token"


def test_register_adds_all_read_tools():
    mcp = FastMCP(name="test")

    read.register(mcp)

    tools = asyncio.run(mcp.list_tools())
    tool_names = {tool.name for tool in tools}
    assert tool_names == {
        "list_sites",
        "get_site",
        "list_devices",
        "get_device",
        "list_interfaces",
        "get_interface",
        "list_ip_addresses",
        "get_ip_address",
        "list_vlans",
        "get_vlan",
    }
    assert all(
        tool.annotations.readOnlyHint and tool.annotations.idempotentHint
        for tool in tools
    )
