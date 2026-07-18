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
