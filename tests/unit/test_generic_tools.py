import asyncio

import httpx
import pytest
from fastmcp import FastMCP

from client.config import ClientSettings
from client.rest import BRANCH_HEADER, NetBoxRestClient
from tools import generic
from tools.response import ResponseTooLargeError


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


def test_search_resources_with_no_query_returns_everything():
    result = generic.search_resources()

    resource_names = {r["resource"] for r in result["results"]}
    assert "rack" in resource_names
    assert "tenant" in resource_names
    assert all({"resource", "label", "rest_path"} == set(r) for r in result["results"])
    assert result["returned"] == result["count"]
    assert result["truncated"] is False


def test_search_resources_filters_by_name_or_label_case_insensitively():
    result = generic.search_resources("rack")

    resource_names = {r["resource"] for r in result["results"]}
    assert resource_names == {"rack", "rack_role", "rack_reservation", "rack_type"}
    assert result["count"] == 4


def test_search_resources_matches_label_not_just_resource_name():
    result = generic.search_resources("VRF")

    assert {r["resource"] for r in result["results"]} == {"vrf"}


def test_search_resources_pages_with_limit_and_offset():
    everything = generic.search_resources()["results"]

    result = generic.search_resources(limit=2, offset=1)

    assert result["results"] == everything[1:3]
    assert result["count"] == len(everything)
    assert result["truncated"] is True
    assert result["next_offset"] == 3


def test_get_resource_with_object_id_fetches_single_object(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/dcim/racks/3/"
        return httpx.Response(200, json={"id": 3, "name": "rack-a"})

    monkeypatch.setattr(generic, "_client", lambda branch=None: make_client(handler))

    assert generic.get_resource("rack", object_id=3) == {"id": 3, "name": "rack-a"}


def test_get_resource_without_object_id_lists_with_filters(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tenancy/tenants/"
        assert request.url.params["name"] == "acme"
        return httpx.Response(
            200,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{"id": 1, "name": "acme"}],
            },
        )

    monkeypatch.setattr(generic, "_client", lambda branch=None: make_client(handler))

    result = generic.get_resource("tenant", filters={"name": "acme"})
    assert result == {
        "count": 1,
        "returned": 1,
        "offset": 0,
        "truncated": False,
        "next_offset": None,
        "results": [{"id": 1, "name": "acme"}],
    }


def big_table_handler(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(
            200,
            json={
                "count": 4000,
                "next": "http://netbox.local/api/dcim/racks/?limit=50&offset=50",
                "previous": None,
                "results": [{"id": i} for i in range(50)],
            },
        )

    return handler


def test_get_resource_without_filters_makes_a_single_request(monkeypatch):
    """NETBOX-113: this used to walk the whole table, page after page."""
    calls = []
    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(big_table_handler(calls))
    )

    result = generic.get_resource("rack")

    assert len(calls) == 1
    assert calls[0].params["limit"] == "50"
    assert result["count"] == 4000
    assert result["returned"] == 50
    assert result["truncated"] is True
    assert result["next_offset"] == 50


def test_get_resource_sends_limit_offset_brief_and_fields(monkeypatch):
    calls = []
    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(big_table_handler(calls))
    )

    generic.get_resource("rack", limit=10, offset=20, brief=True, fields=["id", "name"])

    params = calls[0].params
    assert params["limit"] == "10"
    assert params["offset"] == "20"
    assert params["brief"] == "true"
    assert params["fields"] == "id,name"


def test_get_resource_limit_inside_filters_wins_but_stays_capped(monkeypatch):
    calls = []
    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(big_table_handler(calls))
    )

    generic.get_resource("rack", filters={"limit": 0})

    assert calls[0].params["limit"] == "1000"


def test_get_resource_single_object_sends_field_selection(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/dcim/racks/3/"
        assert request.url.params["brief"] == "true"
        return httpx.Response(200, json={"id": 3, "name": "rack-a"})

    monkeypatch.setattr(generic, "_client", lambda branch=None: make_client(handler))

    assert generic.get_resource("rack", object_id=3, brief=True) == {
        "id": 3,
        "name": "rack-a",
    }


def test_get_resource_single_object_over_the_size_cap_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 3, "comments": "x" * 5000})

    monkeypatch.setenv("MCP_MAX_RESPONSE_BYTES", "2000")
    monkeypatch.setattr(generic, "_client", lambda branch=None: make_client(handler))

    with pytest.raises(ResponseTooLargeError, match="fields"):
        generic.get_resource("rack", object_id=3)


def test_get_resource_raises_value_error_for_unknown_resource():
    with pytest.raises(ValueError, match="Unknown resource"):
        generic.get_resource("not-a-real-resource")


def test_get_resource_schema_returns_client_schema(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "OPTIONS"
        assert request.url.path == "/api/dcim/power-panels/"
        return httpx.Response(
            200,
            json={
                "actions": {
                    "POST": {
                        "id": {
                            "type": "integer",
                            "required": False,
                            "read_only": True,
                            "label": "ID",
                        },
                        "name": {
                            "type": "string",
                            "required": True,
                            "read_only": False,
                            "label": "Name",
                            "max_length": 100,
                        },
                    }
                }
            },
        )

    monkeypatch.setattr(generic, "_client", lambda branch=None: make_client(handler))

    result = generic.get_resource_schema("power_panel")
    assert result == {
        "name": {"type": "string", "required": True, "label": "Name", "max_length": 100}
    }


def test_get_resource_schema_raises_value_error_for_unknown_resource():
    with pytest.raises(ValueError, match="Unknown resource"):
        generic.get_resource_schema("not-a-real-resource")


def test_write_resource_create_posts_payload(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/tenancy/tenants/"
        assert request.headers[BRANCH_HEADER] == "br1"
        return httpx.Response(201, json={"id": 1, "name": "acme"})

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = generic.write_resource(
        "tenant", "create", branch="br1", data={"name": "acme"}
    )
    assert result == {"id": 1, "name": "acme"}


def test_write_resource_patch_updates_object(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/dcim/racks/3/"
        return httpx.Response(200, json={"id": 3, "name": "rack-b"})

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = generic.write_resource(
        "rack", "patch", branch="br1", object_id=3, data={"name": "rack-b"}
    )
    assert result == {"id": 3, "name": "rack-b"}


def test_write_resource_delete_requires_no_data(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/api/dcim/racks/3/"
        return httpx.Response(204)

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    assert (
        generic.write_resource(
            "rack", "delete", branch="br1", object_id=3, confirm=True
        )
        is None
    )


def test_write_resource_delete_without_confirm_is_rejected(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not reach the network without confirm=True")

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    with pytest.raises(ValueError, match="confirmation requise"):
        generic.write_resource("rack", "delete", branch="br1", object_id=3)


def test_write_resource_delete_with_confirm_false_is_rejected(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not reach the network without confirm=True")

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    with pytest.raises(ValueError, match="confirmation requise"):
        generic.write_resource(
            "rack", "delete", branch="br1", object_id=3, confirm=False
        )


def test_write_resource_create_ignores_confirm(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(201, json={"id": 1, "name": "acme"})

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = generic.write_resource(
        "tenant", "create", branch="br1", data={"name": "acme"}
    )
    assert result == {"id": 1, "name": "acme"}


def test_write_resource_raises_value_error_when_object_id_missing():
    with pytest.raises(ValueError, match="object_id is required"):
        generic.write_resource("rack", "patch", branch="br1")


def test_write_resource_raises_value_error_for_unknown_resource():
    with pytest.raises(ValueError, match="Unknown resource"):
        generic.write_resource("not-a-real-resource", "create", branch="br1", data={})


def test_register_adds_all_generic_tools():
    mcp = FastMCP(name="test")

    generic.register(mcp)

    tool_names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert tool_names == {
        "search_resources",
        "get_resource",
        "get_resource_schema",
        "write_resource",
    }


def test_search_and_get_tools_are_read_only():
    mcp = FastMCP(name="test")
    generic.register(mcp)
    tools_by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}

    for name in ("search_resources", "get_resource", "get_resource_schema"):
        assert tools_by_name[name].annotations.readOnlyHint is True
        assert tools_by_name[name].annotations.idempotentHint is True


def test_write_resource_tool_is_destructive_and_not_idempotent():
    mcp = FastMCP(name="test")
    generic.register(mcp)
    tools_by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}

    assert tools_by_name["write_resource"].annotations.destructiveHint is True
    assert tools_by_name["write_resource"].annotations.idempotentHint is False


def test_validate_resource_suggests_close_matches_for_unknown_resource():
    with pytest.raises(ValueError, match=r"did you mean.*power_panel"):
        generic.get_resource("panel")


def test_validate_resource_falls_back_to_search_hint_when_no_matches():
    with pytest.raises(ValueError, match=r"call search_resources\(\)"):
        generic.get_resource("zzzznotreal")
