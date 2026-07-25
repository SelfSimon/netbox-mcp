import httpx
import pytest

from client.config import ClientSettings
from client.exceptions import (
    NetBoxConnectionError,
    NetBoxNoBranchError,
    NetBoxNotFoundError,
    NetBoxPermissionError,
    NetBoxValidationError,
)
from client.rest import BRANCH_HEADER, NetBoxRestClient


def make_client(handler, branch: str | None = None) -> NetBoxRestClient:
    settings = ClientSettings(
        netbox_url="http://netbox.local",
        netbox_api_token="token123",
    )
    rest_client = NetBoxRestClient(settings, branch=branch)
    rest_client._client = httpx.Client(
        base_url="http://netbox.local/api/",
        headers=rest_client._client.headers,
        transport=httpx.MockTransport(handler),
    )
    return rest_client


def test_create_sends_authorization_header_and_returns_json():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(201, json={"id": 1, "name": "sw01"})

    client = make_client(handler)

    result = client.create("device", {"name": "sw01"})

    assert result == {"id": 1, "name": "sw01"}
    assert seen_requests[0].method == "POST"
    assert seen_requests[0].url.path == "/api/dcim/devices/"
    assert seen_requests[0].headers["Authorization"] == "Token token123"


def test_update_sends_put_to_object_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/api/dcim/devices/42/"
        return httpx.Response(200, json={"id": 42})

    client = make_client(handler)

    result = client.update("device", 42, {"name": "sw01"})

    assert result == {"id": 42}


def test_patch_sends_patch_to_object_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/dcim/devices/42/"
        return httpx.Response(200, json={"id": 42, "name": "sw02"})

    client = make_client(handler)

    result = client.patch("device", 42, {"name": "sw02"})

    assert result == {"id": 42, "name": "sw02"}


def test_get_sends_get_to_object_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/dcim/devices/42/"
        return httpx.Response(200, json={"id": 42, "name": "sw01"})

    client = make_client(handler)

    result = client.get("device", 42)

    assert result == {"id": 42, "name": "sw01"}


def test_list_follows_pagination():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        if "offset" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "count": 3,
                    "next": "http://netbox.local/api/dcim/devices/?offset=2",
                    "previous": None,
                    "results": [{"id": 1}, {"id": 2}],
                },
            )
        return httpx.Response(
            200,
            json={
                "count": 3,
                "next": None,
                "previous": "http://netbox.local/api/dcim/devices/",
                "results": [{"id": 3}],
            },
        )

    client = make_client(handler)

    result = client.list("device")

    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(calls) == 2


def test_list_with_explicit_limit_does_not_follow_pagination():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(
            200,
            json={
                "count": 300,
                "next": "http://netbox.local/api/dcim/devices/?limit=10&offset=10",
                "previous": None,
                "results": [{"id": i} for i in range(10)],
            },
        )

    client = make_client(handler)

    result = client.list("device", filters={"limit": 10})

    assert len(result) == 10
    assert len(calls) == 1


def test_list_sends_filters_as_query_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["site"] == "dc1"
        return httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )

    client = make_client(handler)

    client.list("device", filters={"site": "dc1"})


def test_count_returns_count_field():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "1"
        return httpx.Response(
            200, json={"count": 42, "next": None, "previous": None, "results": []}
        )

    client = make_client(handler)

    assert client.count("device") == 42


@pytest.mark.parametrize(
    "status_code,expected_exception",
    [
        (404, NetBoxNotFoundError),
        (403, NetBoxPermissionError),
        (401, NetBoxPermissionError),
        (400, NetBoxValidationError),
        (429, NetBoxConnectionError),
        (500, NetBoxConnectionError),
    ],
)
def test_error_status_codes_map_to_client_exceptions(status_code, expected_exception):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "error"})

    client = make_client(handler)

    with pytest.raises(expected_exception):
        client.create("device", {"name": "sw01"})


def test_timeout_raises_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    client = make_client(handler)

    with pytest.raises(NetBoxConnectionError):
        client.create("device", {"name": "sw01"})


def test_no_branch_sends_no_branch_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert BRANCH_HEADER not in request.headers
        return httpx.Response(200, json={"id": 1})

    client = make_client(handler)

    client.get("device", 1)


def test_active_branch_sends_branch_header_on_every_request():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers[BRANCH_HEADER] == "abc123"
        return httpx.Response(200, json={"id": 1})

    client = make_client(handler, branch="abc123")

    client.get("device", 1)
    assert client.branch == "abc123"


def test_delete_without_active_branch_raises_before_any_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent")

    client = make_client(handler)

    with pytest.raises(NetBoxNoBranchError):
        client.delete("device", 1)


def test_delete_with_active_branch_sends_delete_request():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/api/dcim/devices/1/"
        assert request.headers[BRANCH_HEADER] == "abc123"
        return httpx.Response(204)

    client = make_client(handler, branch="abc123")

    assert client.delete("device", 1) is None


POWER_PANEL_OPTIONS = {
    "actions": {
        "POST": {
            "id": {
                "type": "integer",
                "required": False,
                "read_only": True,
                "label": "ID",
            },
            "url": {
                "type": "url",
                "required": False,
                "read_only": True,
                "label": "Url",
            },
            "display": {
                "type": "string",
                "required": False,
                "read_only": True,
                "label": "Display",
            },
            "site": {
                "type": "nested object",
                "required": True,
                "read_only": False,
                "label": "Site",
                "children": {
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
                    "slug": {
                        "type": "slug",
                        "required": True,
                        "read_only": False,
                        "label": "Slug",
                        "max_length": 100,
                    },
                },
            },
            "location": {
                "type": "nested object",
                "required": False,
                "read_only": False,
                "label": "Location",
                "children": {
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
                    "slug": {
                        "type": "slug",
                        "required": True,
                        "read_only": False,
                        "label": "Slug",
                        "max_length": 100,
                    },
                },
            },
            "name": {
                "type": "string",
                "required": True,
                "read_only": False,
                "label": "Name",
                "max_length": 100,
            },
            "created": {
                "type": "datetime",
                "required": False,
                "read_only": True,
                "label": "Created",
            },
            "last_updated": {
                "type": "datetime",
                "required": False,
                "read_only": True,
                "label": "Last updated",
            },
        }
    }
}

TENANT_OPTIONS = {
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
            "slug": {
                "type": "slug",
                "required": True,
                "read_only": False,
                "label": "Slug",
                "max_length": 100,
            },
            "group": {
                "type": "nested object",
                "required": False,
                "read_only": False,
                "label": "Group",
                "children": {
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
                    "slug": {
                        "type": "slug",
                        "required": True,
                        "read_only": False,
                        "label": "Slug",
                        "max_length": 100,
                    },
                },
            },
            "tags": {
                "type": "field",
                "required": False,
                "read_only": False,
                "label": "Tags",
                "child": {
                    "type": "nested object",
                    "required": False,
                    "read_only": False,
                    "children": {
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
                        "slug": {
                            "type": "slug",
                            "required": True,
                            "read_only": False,
                            "label": "Slug",
                            "max_length": 100,
                        },
                    },
                },
            },
            "comments": {
                "type": "string",
                "required": False,
                "read_only": False,
                "label": "Comments",
                "help_text": "Free-form comments",
            },
            "created": {
                "type": "datetime",
                "required": False,
                "read_only": True,
                "label": "Created",
            },
            "last_updated": {
                "type": "datetime",
                "required": False,
                "read_only": True,
                "label": "Last updated",
            },
        }
    }
}

RACK_OPTIONS = {
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
            "site": {
                "type": "nested object",
                "required": True,
                "read_only": False,
                "label": "Site",
                "children": {
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
                    "slug": {
                        "type": "slug",
                        "required": True,
                        "read_only": False,
                        "label": "Slug",
                        "max_length": 100,
                    },
                },
            },
            "status": {
                "type": "field",
                "required": False,
                "read_only": False,
                "label": "Status",
                "choices": [
                    {"value": "active", "display_name": "Active"},
                    {"value": "planned", "display_name": "Planned"},
                    {"value": "reserved", "display_name": "Reserved"},
                ],
            },
            "u_height": {
                "type": "integer",
                "required": False,
                "read_only": False,
                "label": "Height (U)",
            },
            "created": {
                "type": "datetime",
                "required": False,
                "read_only": True,
                "label": "Created",
            },
        }
    }
}


def test_schema_reduces_nested_objects_to_references_and_drops_read_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "OPTIONS"
        assert request.url.path == "/api/dcim/power-panels/"
        return httpx.Response(200, json=POWER_PANEL_OPTIONS)

    client = make_client(handler)

    assert client.schema("power_panel") == {
        "site": {
            "type": "reference",
            "required": True,
            "label": "Site",
            "reference_by": ["id", "slug", "name"],
        },
        "location": {
            "type": "reference",
            "required": False,
            "label": "Location",
            "reference_by": ["id", "slug", "name"],
        },
        "name": {
            "type": "string",
            "required": True,
            "label": "Name",
            "max_length": 100,
        },
    }


def test_schema_reduces_list_of_nested_objects_to_list_reference():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "OPTIONS"
        assert request.url.path == "/api/tenancy/tenants/"
        return httpx.Response(200, json=TENANT_OPTIONS)

    client = make_client(handler)

    assert client.schema("tenant") == {
        "name": {
            "type": "string",
            "required": True,
            "label": "Name",
            "max_length": 100,
        },
        "slug": {
            "type": "slug",
            "required": True,
            "label": "Slug",
            "max_length": 100,
        },
        "group": {
            "type": "reference",
            "required": False,
            "label": "Group",
            "reference_by": ["id", "slug", "name"],
        },
        "tags": {
            "type": "list[reference]",
            "required": False,
            "label": "Tags",
            "reference_by": ["id", "slug", "name"],
        },
        "comments": {
            "type": "string",
            "required": False,
            "label": "Comments",
            "help_text": "Free-form comments",
        },
    }


def test_schema_keeps_choices_for_enum_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "OPTIONS"
        assert request.url.path == "/api/dcim/racks/"
        return httpx.Response(200, json=RACK_OPTIONS)

    client = make_client(handler)

    assert client.schema("rack") == {
        "name": {
            "type": "string",
            "required": True,
            "label": "Name",
            "max_length": 100,
        },
        "site": {
            "type": "reference",
            "required": True,
            "label": "Site",
            "reference_by": ["id", "slug", "name"],
        },
        "status": {
            "type": "field",
            "required": False,
            "label": "Status",
            "choices": [
                {"value": "active", "display_name": "Active"},
                {"value": "planned", "display_name": "Planned"},
                {"value": "reserved", "display_name": "Reserved"},
            ],
        },
        "u_height": {
            "type": "integer",
            "required": False,
            "label": "Height (U)",
        },
    }


def test_schema_maps_404_to_not_found_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Not found."})

    client = make_client(handler)

    with pytest.raises(NetBoxNotFoundError):
        client.schema("power_panel")
