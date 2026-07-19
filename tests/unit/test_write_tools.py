import httpx
from mcp.server.fastmcp import FastMCP

from client.config import ClientSettings
from client.rest import BRANCH_HEADER, NetBoxRestClient
from schemas.writes import (
    DeviceCreate,
    DeviceUpdate,
    InterfaceCreate,
    InterfaceUpdate,
    IPAddressAssign,
)
from tools import write


def make_client(handler, branch=None) -> NetBoxRestClient:
    settings = ClientSettings(
        netbox_url="http://netbox.local", netbox_api_token="token123"
    )
    client = NetBoxRestClient(settings, branch=branch)
    client._client = httpx.Client(
        base_url="http://netbox.local/api/",
        headers=client._client.headers,
        transport=httpx.MockTransport(handler),
    )
    return client


def test_create_device_posts_payload_scoped_to_branch(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/dcim/devices/"
        assert request.headers[BRANCH_HEADER] == "br_abc123"
        return httpx.Response(201, json={"id": 1, "name": "sw01"})

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    payload = DeviceCreate(name="sw01", device_type=1, role=1, site=1)
    assert write.create_device(payload, branch="br_abc123") == {"id": 1, "name": "sw01"}


def test_update_device_patches_object_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/dcim/devices/42/"
        assert request.headers[BRANCH_HEADER] == "br_abc123"
        return httpx.Response(200, json={"id": 42, "name": "sw02"})

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = write.update_device(42, DeviceUpdate(name="sw02"), branch="br_abc123")
    assert result == {"id": 42, "name": "sw02"}


def test_create_interface_posts_payload(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/dcim/interfaces/"
        return httpx.Response(201, json={"id": 5, "name": "eth0"})

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    payload = InterfaceCreate(device=1, name="eth0", type="1000base-t")
    assert write.create_interface(payload, branch="br1") == {"id": 5, "name": "eth0"}


def test_update_interface_patches_object_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/dcim/interfaces/5/"
        return httpx.Response(200, json={"id": 5, "enabled": False})

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = write.update_interface(5, InterfaceUpdate(enabled=False), branch="br1")
    assert result == {"id": 5, "enabled": False}


def test_assign_ip_address_posts_payload(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/ipam/ip-addresses/"
        return httpx.Response(201, json={"id": 9, "address": "10.0.0.1/24"})

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    payload = IPAddressAssign(address="10.0.0.1/24", assigned_object_id=5)
    result = write.assign_ip_address(payload, branch="br1")
    assert result == {"id": 9, "address": "10.0.0.1/24"}


def test_create_branch_creates_then_waits_until_ready(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            assert request.url.path == "/api/plugins/branching/branches/"
            return httpx.Response(
                201,
                json={"id": 1, "name": "test-branch", "status": {"value": "new"}},
            )
        return httpx.Response(
            200,
            json={
                "id": 1,
                "name": "test-branch",
                "status": {"value": "ready"},
                "schema_id": "br_xyz",
            },
        )

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = write.create_branch("test-branch", "a test branch")

    assert result["status"]["value"] == "ready"
    assert result["schema_id"] == "br_xyz"
    assert ("POST", "/api/plugins/branching/branches/") in calls


def test_list_branches_returns_results(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/plugins/branching/branches/"
        return httpx.Response(
            200,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{"id": 1, "name": "b1"}],
            },
        )

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    assert write.list_branches() == [{"id": 1, "name": "b1"}]


def test_client_uses_caller_token_not_fallback(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local")
    monkeypatch.setenv("NETBOX_API_TOKEN", "fallback-token")
    monkeypatch.setattr("netbox_mcp.auth.get_current_token", lambda: "caller-token")
    monkeypatch.setattr(write, "get_current_token", lambda: "caller-token")

    client = write._client(branch="br1")

    assert client._client.headers["Authorization"] == "Token caller-token"
    assert client._client.headers[BRANCH_HEADER] == "br1"


def test_register_adds_all_write_tools():
    mcp = FastMCP(name="test")

    write.register(mcp)

    tool_names = {tool.name for tool in mcp._tool_manager.list_tools()}
    assert tool_names == {
        "create_device",
        "update_device",
        "create_interface",
        "update_interface",
        "assign_ip_address",
        "create_branch",
        "list_branches",
    }


def test_create_tools_are_not_destructive_and_not_idempotent():
    mcp = FastMCP(name="test")
    write.register(mcp)
    tools_by_name = {t.name: t for t in mcp._tool_manager.list_tools()}

    for name in (
        "create_device",
        "create_interface",
        "assign_ip_address",
        "create_branch",
    ):
        assert tools_by_name[name].annotations.destructiveHint is False
        assert tools_by_name[name].annotations.idempotentHint is False


def test_update_tools_are_destructive_and_idempotent():
    mcp = FastMCP(name="test")
    write.register(mcp)
    tools_by_name = {t.name: t for t in mcp._tool_manager.list_tools()}

    for name in ("update_device", "update_interface"):
        assert tools_by_name[name].annotations.destructiveHint is True
        assert tools_by_name[name].annotations.idempotentHint is True


def test_list_branches_is_read_only():
    mcp = FastMCP(name="test")
    write.register(mcp)
    tools_by_name = {t.name: t for t in mcp._tool_manager.list_tools()}

    assert tools_by_name["list_branches"].annotations.readOnlyHint is True
    assert tools_by_name["list_branches"].annotations.idempotentHint is True
