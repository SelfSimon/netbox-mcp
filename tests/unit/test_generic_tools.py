import asyncio
import json

import httpx
import pytest
from fastmcp import FastMCP

from client.config import ClientSettings
from client.exceptions import NetBoxNotFoundError, NetBoxValidationError
from client.rest import BRANCH_HEADER, MAX_BATCH_SIZE, NetBoxRestClient
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
    assert all(
        {"resource", "label", "rest_path", "writable"} == set(r)
        for r in result["results"]
    )
    assert result["returned"] == result["count"]
    assert result["truncated"] is False


def test_search_resources_filters_by_name_or_label_case_insensitively():
    result = generic.search_resources("rack")

    resource_names = {r["resource"] for r in result["results"]}
    assert resource_names == {"rack", "rack_role", "rack_reservation", "rack_type"}
    assert result["count"] == 4


def test_search_resources_finds_every_component_template():
    result = generic.search_resources("template")

    resource_names = {r["resource"] for r in result["results"]}
    assert {
        "console_port_template",
        "console_server_port_template",
        "device_bay_template",
        "front_port_template",
        "interface_template",
        "inventory_item_template",
        "module_bay_template",
        "power_outlet_template",
        "power_port_template",
        "rear_port_template",
    } <= resource_names


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
        assert tools_by_name[name].annotations.read_only_hint is True
        assert tools_by_name[name].annotations.idempotent_hint is True


def test_write_resource_tool_is_destructive_and_not_idempotent():
    mcp = FastMCP(name="test")
    generic.register(mcp)
    tools_by_name = {t.name: t for t in asyncio.run(mcp.list_tools())}

    assert tools_by_name["write_resource"].annotations.destructive_hint is True
    assert tools_by_name["write_resource"].annotations.idempotent_hint is False


def test_validate_resource_suggests_close_matches_for_unknown_resource():
    with pytest.raises(ValueError, match=r"did you mean.*power_panel"):
        generic.get_resource("panel")


def test_validate_resource_falls_back_to_search_hint_when_no_matches():
    with pytest.raises(ValueError, match=r"call search_resources\(\)"):
        generic.get_resource("zzzznotreal")


def test_search_resources_flags_resources_the_mcp_cannot_write():
    results = {r["resource"]: r for r in generic.search_resources()["results"]}

    assert results["owner"]["writable"] is False
    assert results["webhook"]["writable"] is False
    assert results["device"]["writable"] is True


@pytest.mark.parametrize("action", ["create", "update", "patch", "delete"])
def test_write_resource_refuses_a_non_branchable_resource(monkeypatch, action):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may reach NetBox")

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    with pytest.raises(ValueError) as excinfo:
        generic.write_resource(
            "owner", action, branch="br1", object_id=1, data={}, confirm=True
        )

    message = str(excinfo.value)
    assert "manually in the NetBox UI" in message
    assert "/users/owners/" in message


def test_write_resource_refusal_needs_no_netbox_url_and_links_the_ui_url(
    monkeypatch,
):
    # The refusal is built before any client exists: it must not depend on
    # NETBOX_URL, and links only NETBOX_UI_URL (NETBOX-142).
    monkeypatch.delenv("NETBOX_URL", raising=False)
    monkeypatch.setenv("NETBOX_UI_URL", "https://netbox.example.com/")

    with pytest.raises(ValueError) as excinfo:
        generic.write_resource("owner", "create", branch="br1", data={})

    assert str(excinfo.value).endswith(
        "NetBox UI: https://netbox.example.com/users/owners/"
    )


def test_get_resource_schema_says_a_non_branchable_resource_is_read_only(
    monkeypatch,
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may reach NetBox")

    monkeypatch.setattr(generic, "_client", lambda branch=None: make_client(handler))

    with pytest.raises(ValueError, match="manually in the NetBox UI"):
        generic.get_resource_schema("token")


def test_get_resource_still_reads_a_non_branchable_resource(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 1, "name": "Nord Quantique"})

    monkeypatch.setattr(generic, "_client", lambda branch=None: make_client(handler))

    assert generic.get_resource("owner", object_id=1)["name"] == "Nord Quantique"


def test_get_resource_reads_in_the_branch_it_is_given(monkeypatch):
    # NETBOX-145
    seen = []

    def handler(request):
        seen.append(request.headers.get("X-NetBox-Branch"))
        return httpx.Response(200, json={"count": 0, "next": None, "results": []})

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch)
    )
    generic.get_resource("rack", branch="br1")
    generic.get_resource("rack")
    assert seen == ["br1", None]


# -- Batches (NETBOX-146) ----------------------------------------------------


def _batch_client(monkeypatch, handler):
    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )


def _template(i: int, **extra) -> dict:
    return {
        "id": i,
        "url": f"http://nb/api/dcim/interface-templates/{i}/",
        "display": f"eth{i}",
        "name": f"eth{i}",
        "type": {"value": "1000base-t"},
        **extra,
    }


def test_a_create_batch_is_one_post_of_the_whole_list(monkeypatch):
    sent = []

    def handler(request):
        sent.append((request.method, request.url.path, json.loads(request.content)))
        body = json.loads(request.content)
        return httpx.Response(201, json=[_template(10 + i) for i in range(len(body))])

    _batch_client(monkeypatch, handler)
    data = [
        {"device_type": 1, "name": f"eth{i}", "type": "1000base-t"} for i in range(3)
    ]

    result = generic.write_resource("interface_template", "create", "br1", data=data)

    assert sent == [("POST", "/api/dcim/interface-templates/", data)]
    assert result == {
        "count": 3,
        "results": [
            {
                "id": i,
                "url": f"http://nb/api/dcim/interface-templates/{i}/",
                "display": f"eth{i}",
            }
            for i in (10, 11, 12)
        ],
    }


def test_a_patch_batch_checks_the_ids_then_sends_one_patch(monkeypatch):
    sent = []

    def handler(request):
        sent.append((request.method, str(request.url.params)))
        if request.method == "GET":
            return httpx.Response(
                200, json={"count": 2, "results": [{"id": 4}, {"id": 5}]}
            )
        assert json.loads(request.content) == data
        return httpx.Response(200, json=[_template(4), _template(5)])

    _batch_client(monkeypatch, handler)
    data = [{"id": 4, "name": "up0"}, {"id": 5, "name": "up1"}]

    result = generic.write_resource("interface_template", "patch", "br1", data=data)

    assert sent == [("GET", "id=4&id=5&fields=id&limit=2"), ("PATCH", "")]
    assert [r["id"] for r in result["results"]] == [4, 5]


def test_a_patch_batch_with_an_unknown_id_changes_nothing(monkeypatch):
    # NetBox would skip an unknown id silently and apply the others.
    methods = []

    def handler(request):
        methods.append(request.method)
        return httpx.Response(200, json={"count": 1, "results": [{"id": 4}]})

    _batch_client(monkeypatch, handler)

    with pytest.raises(NetBoxNotFoundError, match=r"id \[999\]; nothing was changed"):
        generic.write_resource(
            "interface_template",
            "patch",
            "br1",
            data=[{"id": 4, "name": "a"}, {"id": 999, "name": "b"}],
        )
    assert methods == ["GET"]


@pytest.mark.parametrize(
    ("data", "match"),
    [
        ([{"id": 4}, {"name": "b"}], r"element 1 has no integer `id`"),
        ([{"id": 4}, {"id": True}], r"element 1 has no integer `id`"),
        ([{"id": 4}, {"id": 4}], r"ids \[4\] appear more than once"),
        ([], r"at least one element"),
        ([{"id": i} for i in range(MAX_BATCH_SIZE + 1)], r"at most 250 elements"),
        ([{"id": 4}, "x"], r"element 1 of the batch is not an object"),
    ],
)
def test_a_malformed_patch_batch_sends_nothing(monkeypatch, data, match):
    def handler(request):
        raise AssertionError(f"no request expected, got {request.method}")

    _batch_client(monkeypatch, handler)
    with pytest.raises(NetBoxValidationError, match=match):
        generic.write_resource("interface_template", "patch", "br1", data=data)


def test_a_rejected_create_batch_names_the_element_and_field(monkeypatch):
    def handler(request):
        return httpx.Response(
            400, json=[{}, {}, {"type": ["nope is not a valid choice."]}, {}]
        )

    _batch_client(monkeypatch, handler)
    with pytest.raises(
        NetBoxValidationError,
        match=r"nothing was written: element 2: type: nope is not a valid choice\.$",
    ):
        generic.write_resource("interface_template", "create", "br1", data=[{}] * 4)


def test_a_rejected_patch_batch_finds_the_element_netbox_does_not_name(monkeypatch):
    # NetBox answers a batch PATCH with one element's errors, no index.
    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"count": 3, "results": [{"id": 4}, {"id": 5}, {"id": 6}]}
            )
        return httpx.Response(400, json={"type": ["nope is not a valid choice."]})

    _batch_client(monkeypatch, handler)
    data = [
        {"id": 4, "type": "1000base-t"},
        {"id": 5, "type": "nope"},
        {"id": 6, "name": "x"},
    ]
    with pytest.raises(
        NetBoxValidationError,
        match=r"nothing was changed: element 1 \(id 5\): type: nope is not",
    ):
        generic.write_resource("interface_template", "patch", "br1", data=data)


def test_a_rejected_patch_batch_says_when_netbox_names_no_element(monkeypatch):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"count": 2, "results": [{"id": 4}, {"id": 5}]}
            )
        return httpx.Response(400, json={"__all__": ["Name already exists."]})

    _batch_client(monkeypatch, handler)
    with pytest.raises(NetBoxValidationError, match=r"an element NetBox does not name"):
        generic.write_resource(
            "interface_template",
            "patch",
            "br1",
            data=[{"id": 4, "name": "dup"}, {"id": 5, "name": "dup"}],
        )


@pytest.mark.parametrize(
    ("action", "kwargs", "match"),
    [
        ("update", {}, r"takes one object at a time"),
        ("delete", {"confirm": True}, r"takes one object at a time"),
        ("patch", {"object_id": 3}, r"a batch takes no object_id"),
    ],
)
def test_a_batch_is_only_for_create_and_patch(action, kwargs, match):
    with pytest.raises(ValueError, match=match):
        generic.write_resource("rack", action, "br1", data=[{"id": 3}], **kwargs)


def test_a_batch_of_a_non_branchable_resource_is_refused():
    with pytest.raises(ValueError, match="netbox_branching does not version"):
        generic.write_resource("owner", "create", "br1", data=[{"name": "x"}])


def test_write_resource_documents_the_batch_limit():
    assert f"at most {MAX_BATCH_SIZE}" in generic.write_resource.__doc__


def test_search_resources_finds_the_plugin_objects_by_plugin_name():
    result = generic.search_resources("netbox_security")

    assert result["count"] == 29
    assert {r["resource"] for r in result["results"]} >= {
        "security_zone",
        "nat_rule",
        "firewall_filter_rule",
    }
    assert all(r["writable"] for r in result["results"])


def test_write_resource_refuses_a_read_only_plugin_resource_with_its_reason():
    with pytest.raises(ValueError) as excinfo:
        generic.write_resource("attachment", "create", branch="br1", data={})

    message = str(excinfo.value)
    assert "file upload" in message
    assert "netbox_branching does not version it" not in message
    assert "/plugins/netbox-attachments/netbox-attachments/" in message
    assert generic.search_resources("attachment")["results"][0]["writable"] is False


def test_write_resource_writes_a_plugin_object_in_the_branch(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/plugins/netbox-security/security-zones/"
        assert request.headers[BRANCH_HEADER] == "br1"
        return httpx.Response(201, json={"id": 7, "url": "u", "display": "dmz"})

    monkeypatch.setattr(
        generic, "_client", lambda branch=None: make_client(handler, branch=branch)
    )

    result = generic.write_resource(
        "security_zone", "create", branch="br1", data={"name": "dmz"}
    )

    assert result["id"] == 7
