import asyncio

import httpx
import pytest
from fastmcp import FastMCP

from client.config import ClientSettings
from client.exceptions import NetBoxNotFoundError
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

    assert write.list_branches() == {
        "count": 1,
        "returned": 1,
        "offset": 0,
        "truncated": False,
        "next_offset": None,
        "results": [{"id": 1, "name": "b1"}],
    }


def test_list_branches_sends_limit_and_offset(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "5"
        assert request.url.params["offset"] == "10"
        return httpx.Response(
            200,
            json={"count": 40, "next": None, "previous": None, "results": [{"id": 1}]},
        )

    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = write.list_branches(limit=5, offset=10)

    assert result["count"] == 40
    assert result["truncated"] is True
    assert result["next_offset"] == 11


def test_write_result_over_the_size_cap_is_reduced_to_a_reference(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "id": 9,
                "url": "http://netbox.local/api/dcim/devices/9/",
                "display": "sw01",
                "config_context": {"blob": "x" * 5000},
            },
        )

    monkeypatch.setenv("MCP_MAX_RESPONSE_BYTES", "2000")
    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = write.create_device(
        DeviceCreate(name="sw01", device_type=1, role=1, site=1), branch="br1"
    )

    assert result["id"] == 9
    assert result["truncated"] is True
    assert "config_context" not in result


def test_client_uses_caller_token(monkeypatch):
    monkeypatch.setenv("NETBOX_URL", "http://netbox.local")
    monkeypatch.setattr("netbox_mcp.auth.get_current_token", lambda: "caller-token")
    monkeypatch.setattr(write, "get_current_token", lambda: "caller-token")

    client = write._client(branch="br1")

    assert client._client.headers["Authorization"] == "Token caller-token"
    assert client._client.headers[BRANCH_HEADER] == "br1"


def test_register_adds_all_write_tools():
    mcp = FastMCP(name="test")

    write.register(mcp)

    tool_names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert tool_names == {
        "create_device",
        "update_device",
        "create_interface",
        "update_interface",
        "assign_ip_address",
        "create_branch",
        "list_branches",
        "get_branch_diff",
    }


def test_create_tools_are_not_destructive_and_not_idempotent():
    mcp = FastMCP(name="test")
    write.register(mcp)
    tools_by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}

    for name in (
        "create_device",
        "create_interface",
        "assign_ip_address",
        "create_branch",
    ):
        assert tools_by_name[name].annotations.destructive_hint is False
        assert tools_by_name[name].annotations.idempotent_hint is False


def test_update_tools_are_destructive_and_idempotent():
    mcp = FastMCP(name="test")
    write.register(mcp)
    tools_by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}

    for name in ("update_device", "update_interface"):
        assert tools_by_name[name].annotations.destructive_hint is True
        assert tools_by_name[name].annotations.idempotent_hint is True


def test_branch_read_tools_are_read_only():
    mcp = FastMCP(name="test")
    write.register(mcp)
    tools_by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}

    for name in ("list_branches", "get_branch_diff"):
        assert tools_by_name[name].annotations.read_only_hint is True
        assert tools_by_name[name].annotations.idempotent_hint is True


def change(id, action, object_type="dcim.site", object_id=1, **data):
    return {
        "id": id,
        "branch": {"id": 3, "name": "add-sites", "status": {"value": "ready"}},
        "object_type": object_type,
        "object_id": object_id,
        "object_repr": f"obj{object_id}",
        "action": {"value": action, "label": action.capitalize()},
        "conflicts": data.get("conflicts"),
        "original_data": data.get("original"),
        "modified_data": data.get("modified"),
        "current_data": data.get("current"),
    }


def diff_handler(changes, seen=None, counts=None):
    counts = counts or {"create": 1, "update": 1, "delete": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/plugins/branching/changes/"
        assert BRANCH_HEADER not in request.headers
        if seen is not None:
            seen.append(request.url.params)
        if request.url.params["limit"] == "1" and "action" in request.url.params:
            count = counts[request.url.params["action"]]
            return httpx.Response(
                200, json={"count": count, "next": None, "results": []}
            )
        return httpx.Response(
            200, json={"count": len(changes), "next": None, "results": changes}
        )

    return handler


def test_get_branch_diff_summarizes_each_change(monkeypatch):
    changes = [
        change(
            1,
            "create",
            object_id=10,
            modified={
                "name": "MTL1",
                "slug": "mtl1",
                "description": "",
                "tenant": None,
                "tags": [],
                "created": "2026-11-21T10:00:00Z",
            },
        ),
        change(
            2,
            "update",
            object_id=11,
            original={"name": "QC1", "status": "planned", "last_updated": "a"},
            modified={"name": "QC1", "status": "active", "last_updated": "b"},
            current={"name": "QC1", "status": "planned", "last_updated": "a"},
        ),
        change(3, "delete", object_id=12, original={"name": "OLD"}),
    ]
    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(diff_handler(changes))
    )

    result = write.get_branch_diff("br_abc123")

    assert result["branch"] == "add-sites"
    assert result["summary"] == {"create": 1, "update": 1, "delete": 1}
    assert result["count"] == 3
    assert result["truncated"] is False
    assert result["results"] == [
        {
            "id": 1,
            "action": "create",
            "object_type": "dcim.site",
            "object_id": 10,
            "object": "obj10",
            "data": {"name": "MTL1", "slug": "mtl1"},
        },
        {
            "id": 2,
            "action": "update",
            "object_type": "dcim.site",
            "object_id": 11,
            "object": "obj11",
            "changes": {"status": {"before": "planned", "after": "active"}},
        },
        {
            "id": 3,
            "action": "delete",
            "object_type": "dcim.site",
            "object_id": 12,
            "object": "obj12",
        },
    ]


def test_get_branch_diff_reports_conflicts_with_main(monkeypatch):
    changes = [
        change(
            1,
            "update",
            conflicts=["status"],
            original={"status": "planned"},
            modified={"status": "active"},
            current={"status": "retired"},
        )
    ]
    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(diff_handler(changes))
    )

    result = write.get_branch_diff("br_abc123")

    assert result["results"][0]["conflicts"] == {
        "status": {"original": "planned", "branch": "active", "main": "retired"}
    }


def test_get_branch_diff_filters_by_schema_id_type_and_action(monkeypatch):
    seen = []
    monkeypatch.setattr(
        write, "_client", lambda branch=None: make_client(diff_handler([], seen))
    )

    result = write.get_branch_diff(
        "br_abc123", object_type="dcim.device", action="update", limit=5, offset=10
    )

    page = seen[0]
    assert page["branch"] == "br_abc123"
    assert page["object_type"] == "dcim.device"
    assert page["action"] == "update"
    assert page["limit"] == "5"
    assert page["offset"] == "10"
    assert page["ordering"] == "object_type,object_id"
    # The summary counts the whole branch: one request per action, without
    # the object_type filter.
    counts = seen[1:]
    assert [c["action"] for c in counts] == ["create", "update", "delete"]
    assert all(c["branch"] == "br_abc123" and "object_type" not in c for c in counts)
    # No change on this page: the branch name falls back to the schema_id.
    assert result["branch"] == "br_abc123"


def test_get_branch_diff_on_an_unknown_branch_says_to_pass_a_schema_id(monkeypatch):
    # What NetBox answers for an unknown `branch` filter value.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "branch": [
                    "Select a valid choice. add-sites is not one of the choices."
                ]
            },
        )

    monkeypatch.setattr(write, "_client", lambda branch=None: make_client(handler))

    with pytest.raises(NetBoxNotFoundError, match="schema_id 'add-sites'"):
        write.get_branch_diff("add-sites")
