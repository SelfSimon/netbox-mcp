"""Entry point of the NetBox MCP server.

Skeleton: base structure only.
Registration of read and write tools will be added once the data client
and the Pydantic schemas are available.
"""

import os

import anyio
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from netbox_mcp.auth import TokenCaptureMiddleware
from tools.read import register as register_read_tools

load_dotenv()

MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8765"))

mcp = FastMCP(
    name="netbox-mcp",
    host=MCP_HOST,
    port=MCP_PORT,
)

register_read_tools(mcp)

# TODO: register the write tools (create/update, branch management)
#
# Handlers build their NetBoxRestClient from netbox_mcp.auth.get_current_token()
# (the caller's own NetBox token, passed through per request), not from a
# shared service account token.


async def _run() -> None:
    # HTTP transport (streamable-http): reachable via mcp-remote on the LAN/VPN,
    # per the scoping decision (no public exposure).
    #
    # Not using mcp.run(): we need our own token-capture middleware on the
    # ASGI app, so the app is built and served here instead, the same way
    # FastMCP.run_streamable_http_async() does internally.
    app = mcp.streamable_http_app()
    app.add_middleware(TokenCaptureMiddleware)

    config = uvicorn.Config(app, host=MCP_HOST, port=MCP_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
