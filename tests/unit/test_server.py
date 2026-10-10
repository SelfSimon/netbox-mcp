import asyncio
import json

import httpx
from fastmcp import Client

from client.config import ClientSettings
from client.rest import NetBoxRestClient
from netbox_mcp.server import INSTRUCTIONS, mcp
from tools import read


def test_initialize_returns_the_server_instructions():
    """NETBOX-108: the cross-tool rules travel in `InitializeResult`."""

    async def initialize():
        async with Client(mcp) as client:
            return client.initialize_result.instructions

    instructions = asyncio.run(initialize())

    assert instructions == INSTRUCTIONS
    for keyword in ("create_branch", "get_resource_schema", "patch", "next_offset"):
        assert keyword in instructions


def test_truncated_list_stays_under_one_megabyte_on_the_wire(monkeypatch):
    """NETBOX-116: the cap is measured on the result, but what must fit in
    the client's ~1 MB limit is the whole JSON-RPC message FastMCP emits."""
    devices = [{"id": i, "config_context": {"blob": "x" * 20_000}} for i in range(50)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"count": 50, "next": None, "previous": None, "results": devices},
        )

    def make_client() -> NetBoxRestClient:
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

    monkeypatch.delenv("MCP_MAX_RESPONSE_BYTES", raising=False)
    monkeypatch.setattr(read, "_client", make_client)

    async def call():
        async with Client(mcp) as client:
            return await client.call_tool_mcp("list_devices", {})

    result = asyncio.run(call())

    wire_bytes = len(result.model_dump_json().encode())
    payload = json.loads(result.content[0].text)
    assert payload["truncated"] is True
    assert 0 < payload["returned"] < 50
    assert wire_bytes < 1_000_000
