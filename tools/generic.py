"""Generic search + CRUD tools for NetBox resources without a dedicated tool.

`client/rest.py` and `client/registry.py` are already resource-name-generic
(no per-object Pydantic schema needed — NetBox's own REST API validates).
site/device/interface/ip_address/vlan get dedicated tools in
`tools/read.py`/`tools/write.py` because they're high-usage enough to
warrant precise schemas and per-action MCP annotations; every other
resource registered in `client/registry.py` (the long tail: rack, cable,
vrf, prefix, tenant, circuit, ...) is reachable through the four tools
below instead of a new dedicated tool per object type — including
get_resource_schema() to discover a resource's required/optional fields
before calling write_resource(). See docs/OBJECT_COVERAGE.md for what's
covered which way.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from pydantic import Field

from client.config import get_settings, get_ui_url
from client.registry import get_model_spec, iter_model_specs
from client.rest import (
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    NetBoxRestClient,
    not_branchable_message,
)
from netbox_mcp.auth import get_current_token
from tools.response import (
    batch_response,
    list_response,
    object_response,
    selection_params,
    write_response,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP


# The registry is a short static list: this default returns all of it in one
# call while still keeping search_resources() bounded like every other list.
_SEARCH_DEFAULT_LIMIT = 200

_Limit = Annotated[int, Field(ge=1, le=MAX_LIST_LIMIT)]
_Offset = Annotated[int, Field(ge=0)]


def _client(branch: str | None = None) -> NetBoxRestClient:
    settings = replace(get_settings(), netbox_api_token=get_current_token())
    return NetBoxRestClient(settings, branch=branch)


def _validate_resource(resource: str) -> None:
    try:
        get_model_spec(resource)
    except KeyError:
        needle = resource.strip().lower()
        suggestions = [
            name
            for name, spec in iter_model_specs()
            if needle and needle in f"{name} {spec.label}".lower()
        ][:5]
        hint = (
            f"did you mean one of {suggestions!r}?"
            if suggestions
            else "call search_resources() to list valid resource names."
        )
        raise ValueError(f"Unknown resource {resource!r} — {hint}") from None


def _validate_writable(resource: str) -> None:
    """Refuse resources netbox_branching does not version (NETBOX-142): a
    write would reach main directly, so they are created by hand."""
    spec = get_model_spec(resource)
    if not spec.branchable:
        raise ValueError(not_branchable_message(resource, spec, get_ui_url()))


def search_resources(
    query: str = "",
    limit: _Limit = _SEARCH_DEFAULT_LIMIT,
    offset: _Offset = 0,
) -> dict[str, Any]:
    """List NetBox resource types registered in client/registry.py,
    optionally narrowed by a substring `query` matched against the
    resource name and its NetBox label (case-insensitive).

    Use this to find the `resource` argument for get_resource() and
    write_resource() when no dedicated tool covers the object type you
    need (dedicated tools: site, device, interface, ip_address, vlan —
    prefer those when they apply).

    `writable` is false for the resources netbox_branching does not
    version (users, groups, permissions, tokens, owners, custom fields,
    webhooks, event rules, ...): they can be read, but write_resource()
    refuses them — the user creates or changes them in the NetBox UI.

    Returns `{count, returned, offset, truncated, next_offset, results}`;
    the default `limit` covers the whole registry in one call.
    """
    needle = query.strip().lower()
    matches = []
    for name, spec in iter_model_specs():
        haystack = f"{name} {spec.label}".lower()
        if needle and needle not in haystack:
            continue
        matches.append(
            {
                "resource": name,
                "label": spec.label,
                "rest_path": spec.rest_path,
                "writable": spec.branchable,
            }
        )
    return list_response(
        {
            "count": len(matches),
            "offset": offset,
            "results": matches[offset : offset + limit],
        }
    )


def get_resource(
    resource: str,
    object_id: int | None = None,
    filters: dict[str, Any] | None = None,
    limit: _Limit = DEFAULT_LIST_LIMIT,
    offset: _Offset = 0,
    brief: bool = False,
    fields: list[str] | None = None,
    branch: str | None = None,
) -> Any:
    """Read a NetBox object of any resource type registered in
    client/registry.py (see search_resources() for valid names).

    Pass `object_id` to fetch a single object; otherwise `filters` (raw
    NetBox REST query params, e.g. {"name": "dc1"}) narrows a list, or
    omit both to list the first page.

    Pass `branch`, the `schema_id` of a branch from list_branches(), to
    read as of that branch, its unmerged writes included; without it,
    reads `main`. Resources search_resources() marks `writable: false`
    are not versioned: they read the same with or without a branch.

    A list is returned as `{count, returned, offset, truncated,
    next_offset, results}`: `count` is the total matching in NetBox, and
    `truncated` means there is more — continue from `next_offset`. It
    holds at most `limit` objects (default 50, max 1000), never the whole
    table.

    `brief=True` returns NetBox's minimal representation (id, url,
    display, name and a few key fields — no custom fields, tags or related
    objects); `fields` (e.g. ["id", "name", "status"]) returns only the
    fields you name. Use one of them to inventory many objects in a single
    call.
    """
    _validate_resource(resource)
    selection = selection_params(brief, fields)
    with _client(branch or None) as client:
        if object_id is not None:
            return object_response(client.get(resource, object_id, selection))
        params = {"limit": limit, **(filters or {}), **selection}
        if offset:
            params.setdefault("offset", offset)
        return list_response(client.list_page(resource, params))


def get_resource_schema(resource: str) -> dict[str, Any]:
    """Look up the write schema for a NetBox resource type registered in
    client/registry.py (see search_resources() for valid names).

    Returns a simplified per-field description of what write_resource()
    accepts: required/optional, type, label, valid choices for enum
    fields, and — for fields referencing another object (e.g. `site` on
    `power_panel`) — which of id/slug/name to pass to reference an
    existing object, not that object's own writable fields. Recommended
    before write_resource() on any resource without a dedicated tool
    (site, device, interface, ip_address, vlan already have precise
    Pydantic schemas for their standard fields). Always targets `main`: a
    resource's fields are the same in every branch.

    `custom_fields` lists the custom fields defined for that object type
    under `fields`, each with its type, whether it is required and, for
    a selection, its `choice_set` (read its values with
    get_resource("custom_field_choice_set", object_id=...)). Call it for
    a dedicated resource too (e.g. "device") before setting
    `custom_fields` with its write tool.

    Refused for resources search_resources() marks `writable: false`.
    """
    _validate_resource(resource)
    _validate_writable(resource)
    with _client() as client:
        return object_response(
            client.schema(resource), hint="this schema cannot be returned in full"
        )


def write_resource(
    resource: str,
    action: Literal["create", "update", "patch", "delete"],
    branch: str,
    object_id: int | None = None,
    data: dict[str, Any] | list[dict[str, Any]] | None = None,
    confirm: bool = False,
) -> Any:
    """Create, update, patch, or delete a NetBox object of any resource
    type registered in client/registry.py (see search_resources()),
    inside a netbox_branching branch.

    `branch` should be the schema_id you already obtained from
    create_branch() for this task, same rule as every dedicated write
    tool. `data` is the raw NetBox REST payload — there's no Pydantic
    validation here, NetBox's own API validates and reports errors. Call
    get_resource_schema(resource) first if you're unsure which fields are
    required, optional, or which enum values are valid. `object_id` is
    required for update/patch/delete.

    `action="update"` is a full replacement (HTTP PUT): `data` must
    include every required field of the object, not just the ones you're
    changing — NetBox rejects a PUT that omits a required field, even if
    that field's value wouldn't change. To change only some fields, use
    `action="patch"` (HTTP PATCH) instead; it only needs the fields you
    want to modify. When in doubt, prefer `patch`.

    `action="delete"` additionally requires `confirm=True` — it is
    rejected otherwise. `create`/`update`/`patch` ignore `confirm`.

    Custom fields go in `data["custom_fields"]` as {name: value}; a patch
    changes only the custom fields it names, and null clears one.

    Batches: to create or patch many objects of one resource, pass `data`
    as a list in ONE call instead of one call per object (at most 250
    elements; split larger sets). `create` takes a list of payloads;
    `patch` takes a list where each element holds the `id` of its object
    plus the fields to change, with no `object_id`. A batch is all or
    nothing: if any element is rejected, nothing is written, and the
    error names the element by its index in `data`. A batch returns
    `{count, results}`, one `{id, url, display}` per element in the order
    of `data`. `update` and `delete` take one object at a time.

    Resources marked `writable: false` by search_resources() are refused
    for every action: netbox_branching does not version them, so the
    write would land directly on main. Tell the user to create or change
    them manually in the NetBox UI.
    """
    _validate_resource(resource)
    _validate_writable(resource)
    if isinstance(data, list):
        return _write_batch(resource, action, branch, object_id, data)
    if action != "create" and object_id is None:
        raise ValueError(f"object_id is required for action={action!r}")
    if action == "delete" and not confirm:
        raise ValueError(
            "confirmation requise: pass confirm=True to delete this object"
        )

    with _client(branch) as client:
        if action == "create":
            return write_response(client.create(resource, data or {}))
        if action == "update":
            return write_response(
                client.update(resource, object_id, data or {})  # type: ignore[arg-type]
            )
        if action == "patch":
            return write_response(
                client.patch(resource, object_id, data or {})  # type: ignore[arg-type]
            )
        client.delete(resource, object_id)  # type: ignore[arg-type]
        return None


def _write_batch(
    resource: str,
    action: str,
    branch: str,
    object_id: int | None,
    data: list[dict[str, Any]],
) -> dict[str, Any]:
    if action not in ("create", "patch"):
        raise ValueError(
            f"action={action!r} takes one object at a time: pass `data` as a "
            "single object (batches are for create and patch)"
        )
    if object_id is not None:
        raise ValueError(
            "a batch takes no object_id: put the `id` of each object in its "
            "element of `data`"
        )
    with _client(branch) as client:
        if action == "create":
            return batch_response(client.create_many(resource, data))
        return batch_response(client.patch_many(resource, data))


_SEARCH_ANNOTATIONS = ToolAnnotations(read_only_hint=True, idempotent_hint=True)
_GET_ANNOTATIONS = ToolAnnotations(read_only_hint=True, idempotent_hint=True)
_WRITE_ANNOTATIONS = ToolAnnotations(destructive_hint=True, idempotent_hint=False)


def register(mcp: FastMCP) -> None:
    """Register the generic search/get/schema/write tools on `mcp`."""
    mcp.add_tool(Tool.from_function(search_resources, annotations=_SEARCH_ANNOTATIONS))
    mcp.add_tool(Tool.from_function(get_resource, annotations=_GET_ANNOTATIONS))
    mcp.add_tool(Tool.from_function(get_resource_schema, annotations=_GET_ANNOTATIONS))
    mcp.add_tool(Tool.from_function(write_resource, annotations=_WRITE_ANNOTATIONS))
