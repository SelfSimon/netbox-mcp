"""Generic search + CRUD tools for NetBox resources without a dedicated tool.

`client/rest.py` and `client/registry.py` are already resource-name-generic
(no per-object Pydantic schema needed — NetBox's own REST API validates).
site/device/interface/ip_address/vlan get dedicated tools in
`tools/read.py`/`tools/write.py` because they're high-usage enough to
warrant precise schemas and per-action MCP annotations; every other
resource registered in `client/registry.py` (the long tail: rack, cable,
vrf, prefix, tenant, circuit, ...) is reachable through the three tools
below instead of a new dedicated tool per object type. See
docs/OBJECT_COVERAGE.md for what's covered which way.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from client.config import get_settings
from client.registry import get_model_spec, iter_model_specs
from client.rest import NetBoxRestClient
from netbox_mcp.auth import get_current_token

if TYPE_CHECKING:
    from fastmcp import FastMCP


def _client(branch: str | None = None) -> NetBoxRestClient:
    settings = replace(get_settings(), netbox_api_token=get_current_token())
    return NetBoxRestClient(settings, branch=branch)


def _validate_resource(resource: str) -> None:
    try:
        get_model_spec(resource)
    except KeyError:
        raise ValueError(
            f"Unknown resource {resource!r} — call search_resources() to "
            "list valid resource names."
        ) from None


def search_resources(query: str = "") -> list[dict[str, str]]:
    """List NetBox resource types registered in client/registry.py,
    optionally narrowed by a substring `query` matched against the
    resource name and its NetBox label (case-insensitive).

    Use this to find the `resource` argument for get_resource() and
    write_resource() when no dedicated tool covers the object type you
    need (dedicated tools: site, device, interface, ip_address, vlan —
    prefer those when they apply).
    """
    needle = query.strip().lower()
    matches = []
    for name, spec in iter_model_specs():
        haystack = f"{name} {spec.label}".lower()
        if needle and needle not in haystack:
            continue
        matches.append(
            {"resource": name, "label": spec.label, "rest_path": spec.rest_path}
        )
    return matches


def get_resource(
    resource: str,
    object_id: int | None = None,
    filters: dict[str, Any] | None = None,
) -> Any:
    """Read a NetBox object of any resource type registered in
    client/registry.py (see search_resources() for valid names).

    Pass `object_id` to fetch a single object; otherwise `filters` (raw
    NetBox REST query params, e.g. {"name": "dc1"}) narrows a list, or
    omit both to list everything. Always targets `main` — no branch
    scoping, same as the dedicated read tools.
    """
    _validate_resource(resource)
    with _client() as client:
        if object_id is not None:
            return client.get(resource, object_id)
        return client.list(resource, filters)


def write_resource(
    resource: str,
    action: Literal["create", "update", "patch", "delete"],
    branch: str,
    object_id: int | None = None,
    data: dict[str, Any] | None = None,
) -> Any:
    """Create, update, patch, or delete a NetBox object of any resource
    type registered in client/registry.py (see search_resources()),
    inside a netbox_branching branch.

    `branch` should be the schema_id you already obtained from
    create_branch() for this task, same rule as every dedicated write
    tool. `data` is the raw NetBox REST payload — there's no Pydantic
    validation here, NetBox's own API validates and reports errors.
    `object_id` is required for update/patch/delete.

    `action="update"` is a full replacement (HTTP PUT): `data` must
    include every required field of the object, not just the ones you're
    changing — NetBox rejects a PUT that omits a required field, even if
    that field's value wouldn't change. To change only some fields, use
    `action="patch"` (HTTP PATCH) instead; it only needs the fields you
    want to modify. When in doubt, prefer `patch`.
    """
    _validate_resource(resource)
    if action != "create" and object_id is None:
        raise ValueError(f"object_id is required for action={action!r}")

    with _client(branch) as client:
        if action == "create":
            return client.create(resource, data or {})
        if action == "update":
            return client.update(resource, object_id, data or {})  # type: ignore[arg-type]
        if action == "patch":
            return client.patch(resource, object_id, data or {})  # type: ignore[arg-type]
        client.delete(resource, object_id)  # type: ignore[arg-type]
        return None


_SEARCH_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, idempotentHint=True)
_GET_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, idempotentHint=True)
_WRITE_ANNOTATIONS = ToolAnnotations(destructiveHint=True, idempotentHint=False)


def register(mcp: "FastMCP") -> None:
    """Register the generic search/get/write tools on `mcp`."""
    mcp.add_tool(Tool.from_function(search_resources, annotations=_SEARCH_ANNOTATIONS))
    mcp.add_tool(Tool.from_function(get_resource, annotations=_GET_ANNOTATIONS))
    mcp.add_tool(Tool.from_function(write_resource, annotations=_WRITE_ANNOTATIONS))
