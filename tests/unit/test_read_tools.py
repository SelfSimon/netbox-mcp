import httpx
from mcp.server.fastmcp import FastMCP

from client.config import ClientSettings
from client.rest import NetBoxRestClient
from schemas.choices import DeviceStatus
from schemas.filters import DeviceFilter, SiteFilter
from tools import read


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

    assert read.list_sites(SiteFilter(status="active")) == []


def test_list_sites_defaults_to_no_filters_when_omitted(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == {}
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


def test_client_uses_caller_token_not_fallback(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local")
    monkeypatch.setenv("NETBOX_API_TOKEN", "fallback-token")
    monkeypatch.setattr("netbox_mcp.auth.get_current_token", lambda: "caller-token")
    monkeypatch.setattr(read, "get_current_token", lambda: "caller-token")

    client = read._client()

    assert client._client.headers["Authorization"] == "Token caller-token"


def test_register_adds_all_read_tools():
    mcp = FastMCP(name="test")

    read.register(mcp)

    tool_names = {tool.name for tool in mcp._tool_manager.list_tools()}
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
        for tool in mcp._tool_manager.list_tools()
    )
