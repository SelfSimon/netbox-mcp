import httpx
import pytest

from client.branches import create_branch, get_branch, list_branches, wait_until_ready
from client.config import ClientSettings
from client.exceptions import NetBoxClientError
from client.rest import NetBoxRestClient


def make_client(handler) -> NetBoxRestClient:
    settings = ClientSettings(
        netbox_url="http://netbox.local",
        netbox_api_token="token123",
    )
    rest_client = NetBoxRestClient(settings)
    rest_client._client = httpx.Client(
        base_url="http://netbox.local/api/",
        headers=rest_client._client.headers,
        transport=httpx.MockTransport(handler),
    )
    return rest_client


def status(value: str) -> dict:
    return {"value": value, "label": value.capitalize()}


def test_create_branch_posts_name_and_description():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            201, json={"id": 7, "name": "my-branch", "status": status("new")}
        )

    client = make_client(handler)

    result = create_branch(client, "my-branch", description="test branch")

    assert result["id"] == 7
    assert seen_requests[0].method == "POST"
    assert seen_requests[0].url.path == "/api/plugins/branching/branches/"
    import json

    assert json.loads(seen_requests[0].content) == {
        "name": "my-branch",
        "description": "test branch",
    }


def test_get_branch_returns_branch():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/plugins/branching/branches/7/"
        return httpx.Response(200, json={"id": 7, "status": status("ready")})

    client = make_client(handler)

    result = get_branch(client, 7)

    assert result["id"] == 7


def test_list_branches_follows_pagination():
    def handler(request: httpx.Request) -> httpx.Response:
        if "offset" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "count": 2,
                    "next": "http://netbox.local/api/plugins/branching/branches/?offset=1",
                    "previous": None,
                    "results": [{"id": 1}],
                },
            )
        return httpx.Response(
            200,
            json={"count": 2, "next": None, "previous": None, "results": [{"id": 2}]},
        )

    client = make_client(handler)

    result = list_branches(client)

    assert result == [{"id": 1}, {"id": 2}]


def test_wait_until_ready_returns_immediately_if_already_ready():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 7, "status": status("ready")})

    client = make_client(handler)

    result = wait_until_ready(client, 7, timeout=5, poll_interval=0.01)

    assert result["status"]["value"] == "ready"


def test_wait_until_ready_polls_until_ready(monkeypatch):
    responses = iter([status("new"), status("provisioning"), status("ready")])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 7, "status": next(responses)})

    monkeypatch.setattr("client.branches.time.sleep", lambda _: None)
    client = make_client(handler)

    result = wait_until_ready(client, 7, timeout=5, poll_interval=0.01)

    assert result["status"]["value"] == "ready"


def test_wait_until_ready_raises_on_failed_status(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 7, "status": status("failed")})

    monkeypatch.setattr("client.branches.time.sleep", lambda _: None)
    client = make_client(handler)

    with pytest.raises(NetBoxClientError):
        wait_until_ready(client, 7, timeout=5, poll_interval=0.01)


def test_wait_until_ready_raises_on_timeout(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 7, "status": status("provisioning")})

    times = iter([0, 1, 2, 100])
    monkeypatch.setattr("client.branches.time.monotonic", lambda: next(times))
    monkeypatch.setattr("client.branches.time.sleep", lambda _: None)
    client = make_client(handler)

    with pytest.raises(NetBoxClientError):
        wait_until_ready(client, 7, timeout=5, poll_interval=0.01)


def test_branches_module_has_no_merge_sync_revert_archive():
    import client.branches as branches_module

    for forbidden in ("merge", "sync", "revert", "archive"):
        assert not hasattr(branches_module, forbidden)
