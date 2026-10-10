"""Entry point of the NetBox MCP server: builds the FastMCP app, registers
the read, write and generic tools, and serves it over streamable HTTP.
"""

import os

import anyio
import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.middleware import Middleware

from netbox_mcp.auth import TokenCaptureMiddleware
from tools.generic import register as register_generic_tools
from tools.read import register as register_read_tools
from tools.write import register as register_write_tools

load_dotenv()

MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8765"))

# Server-wide guidance returned in `InitializeResult.instructions`
# (NETBOX-108). Not every MCP client passes it on to the model, so each
# tool's own description stays the source of truth: this only repeats the
# rules that span several tools.
INSTRUCTIONS = """\
This server reads and writes a NetBox instance over its REST API.

Reads always target `main`. Every `list_*` tool, get_resource() without an
`object_id`, search_resources() and list_branches() return an envelope:
`{count, returned, offset, truncated, next_offset, results}`. `count` is the
total in NetBox; when `truncated` is true you have not seen everything —
call again with `offset=next_offset`, or narrow the filters. Lists hold 50
objects by default (max 1000). To inventory many objects in one call, pass
`fields=[...]` with just the fields you need, or `brief=True` for NetBox's
minimal representation (no custom fields, tags or related objects).

Writes never touch `main`: every write tool needs a `branch`, the
`schema_id` of a netbox_branching branch. Create ONE branch per task with
create_branch() and reuse it for every related write; check list_branches()
before creating another. Merging a branch is a human action in the NetBox
UI — this server cannot do it, so tell the user which branch to review.

site, device, interface, ip_address and vlan have dedicated tools; prefer
them. For any other object type, find its name with search_resources(),
then use get_resource() / write_resource(). Call get_resource_schema()
before write_resource() to learn the required fields and valid values.
With write_resource(), prefer `action="patch"` (only the fields you change)
over `action="update"` (a full replacement that needs every required
field). `action="delete"` needs `confirm=True`.
"""

mcp = FastMCP(name="netbox-mcp", instructions=INSTRUCTIONS)

register_read_tools(mcp)
register_write_tools(mcp)
register_generic_tools(mcp)


async def _run() -> None:
    # HTTP transport (streamable-http): reachable via mcp-remote on the LAN/VPN,
    # per the scoping decision (no public exposure).
    #
    # Not using mcp.run(): we need our own token-capture middleware on the
    # ASGI app, so the app is built and served here instead.
    app = mcp.http_app(middleware=[Middleware(TokenCaptureMiddleware)])

    config = uvicorn.Config(app, host=MCP_HOST, port=MCP_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    anyio.run(_run)


if __name__ == "__main__":
    main()
