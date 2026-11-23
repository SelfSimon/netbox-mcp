"""build_device_view(): generate a netbox_device_view grid (NETBOX-150).

The layout logic is in tools/device_view_layout.py; this module reads the
device type and its component templates, and writes the resulting
`grid_template_area` to the device type's device view in a branch.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from client.config import get_settings
from client.rest import MAX_LIST_LIMIT, NetBoxRestClient
from netbox_mcp.auth import get_current_token
from tools.device_view_layout import (
    TEMPLATE_RESOURCES,
    LayoutBand,
    LayoutSection,
    Port,
    build_layout,
    ports_from_templates,
)
from tools.response import object_response, write_response

if TYPE_CHECKING:
    from fastmcp import FastMCP

# How many port names a refusal lists before summarising the rest.
_LISTED_PORTS = 100


def _client(branch: str | None = None) -> NetBoxRestClient:
    settings = replace(get_settings(), netbox_api_token=get_current_token())
    return NetBoxRestClient(settings, branch=branch)


def _ports(client: NetBoxRestClient, device_type: int) -> list[Port]:
    templates = {
        kind: client.list(
            resource,
            {
                "device_type_id": device_type,
                "ordering": "name",
                "limit": MAX_LIST_LIMIT,
            },
            paginate=True,
        )
        for kind, resource in TEMPLATE_RESOURCES.items()
    }
    return ports_from_templates(templates)


def _view_of(client: NetBoxRestClient, device_type: int) -> dict[str, Any] | None:
    """The device view of `device_type`, if it has one.

    netbox_device_view's API ignores every filter (its viewset has no
    filterset: `?device_type=` returns all the views), so the views are
    read in full and matched here. There is one per device type at most,
    so this stays a few pages.
    """
    for view in client.list("device_view", {"limit": MAX_LIST_LIMIT}, paginate=True):
        linked = view.get("device_type")
        if isinstance(linked, dict):
            linked = linked.get("id")
        if linked == device_type:
            return view
    return None


def _port_summary(ports: list[Port]) -> str:
    names = ", ".join(f"{port.name} ({port.kind})" for port in ports[:_LISTED_PORTS])
    more = len(ports) - _LISTED_PORTS
    return names + (f", and {more} more" if more > 0 else "")


def _port_entry(port: Port) -> dict[str, str]:
    return {"name": port.name, "kind": port.kind, "stylename": port.stylename}


def build_device_view(
    device_type: int,
    sections: list[LayoutSection] | None = None,
    bands: list[LayoutBand] | None = None,
    branch: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Generate the netbox_device_view front-panel grid of a device type
    from a description of where its ports physically are, and (unless
    `dry_run`) save it as that device type's device view in a branch.

    The description must come from the real equipment — the vendor's
    datasheet or front-panel drawing, or the user. Never invent one: if
    you don't know where the ports are, ask the user. Without `sections`
    or `bands` the tool refuses, and lists the device type's ports.

    The grid has 2 rows per U (u_height). Describe it left to right as
    `sections`, each spanning every row:
    - `{"ports": [...], "pattern": ...}` — ports by template name, or as
      ranges like "GigabitEthernet1/0/1-48". `pattern`: `top-odd` (1 above
      2, 3 above 4: the usual switch), `top-even` (2 above 1), `row-major`
      (1-24 on the top row, 25-48 below: a patch panel), or `all` (every
      port on row `row`). Set `kind` (interface, console_port, front_port,
      rear_port) if a name exists as several templates;
    - `{"spacer": N}` — N empty gap columns (between port groups);
    - `{"blank": N}` — N columns of plain chassis (panel margins).
    For a device whose rows differ (e.g. 2U with two port rows per U), pass
    `bands` instead: a list of `{"rows": R, "sections": [...]}`, top to
    bottom, whose rows add up to 2 × u_height. A narrower band is padded
    with a blank on the right.

    Example, a 1U 24-port switch with 2 uplinks after a gap:
    sections=[{"blank": 2}, {"ports": ["GigabitEthernet1/0/1-24"]},
    {"spacer": 1}, {"ports": ["TenGigabitEthernet1/1/1-2"]}, {"blank": 2}]

    The grid is refused if a port is unknown, ambiguous or placed twice,
    if a port's stylename can't be a CSS grid area, or if the rows don't
    add up. `unplaced` lists the ports left out, and `collisions` the
    ports the plugin would draw on top of each other (same stylename);
    both are reported, not refused.

    `dry_run=True` (the default) only returns the grid: show it to the user
    before writing. `dry_run=False` needs `branch` (a schema_id): it
    creates the device type's device view there, or patches its
    `grid_template_area` if it has one. Reads use `branch` too when given.
    """
    if not dry_run and not branch:
        raise ValueError(
            "dry_run=False writes the device view: pass `branch`, the schema_id "
            "of the branch for this task"
        )
    if sections and bands:
        raise ValueError("pass either `sections` or `bands`, not both")

    with _client(branch or None) as client:
        dtype = client.get("device_type", device_type)
        u_height = float(dtype.get("u_height") or 0)
        total_rows = math.ceil(u_height * 2)
        ports = _ports(client, device_type)

        if not sections and not bands:
            raise ValueError(
                "describe the layout of the real front panel in `sections` (or "
                "`bands`), from the vendor's documentation or the user — this "
                "tool never guesses one. "
                f"{dtype.get('display', device_type)} ({u_height:g}U, "
                f"{total_rows} rows) has {len(ports)} ports: "
                + (_port_summary(ports) or "none")
            )
        if total_rows == 0:
            raise ValueError(
                f"{dtype.get('display', device_type)} is 0U: netbox_device_view "
                "draws no grid for it"
            )
        if not ports:
            raise ValueError(
                f"{dtype.get('display', device_type)} has no interface, console, "
                "front or rear port template to place"
            )

        layout_bands = bands or [LayoutBand(rows=total_rows, sections=sections or [])]
        layout = build_layout(ports, layout_bands, total_rows)

        result: dict[str, Any] = {
            "device_type": {
                "id": dtype["id"],
                "display": dtype.get("display"),
                "u_height": u_height,
            },
            "rows": len(layout.grid),
            "columns": len(layout.grid[0]),
            "grid": [" ".join(line) for line in layout.grid],
            "grid_template_area": layout.css,
            "placed": len(layout.placed),
            "unplaced": [_port_entry(port) for port in layout.unplaced],
            "collisions": {
                name: [port.name for port in group]
                for name, group in layout.collisions.items()
            },
            "warnings": layout.warnings,
            "dry_run": dry_run,
        }
        if dry_run:
            return object_response(result, hint="describe fewer ports at a time")

        view = _view_of(client, device_type)
        if view is not None:
            if (view.get("yaml_layout") or "").strip():
                result["warnings"].append(
                    "this device view also has a yaml_layout, which the plugin "
                    "renders instead of grid_template_area: clear it in the "
                    "NetBox UI for this grid to show"
                )
            written = client.patch(
                "device_view", view["id"], {"grid_template_area": layout.css}
            )
            result["action"] = "patched"
        else:
            written = client.create(
                "device_view",
                {"device_type": device_type, "grid_template_area": layout.css},
            )
            result["action"] = "created"
        result["branch"] = branch
        result["device_view"] = write_response(
            {key: written[key] for key in ("id", "url", "display") if key in written}
        )
        return object_response(result, hint="describe fewer ports at a time")


_ANNOTATIONS = ToolAnnotations(destructive_hint=True, idempotent_hint=True)


def register(mcp: FastMCP) -> None:
    """Register build_device_view() on `mcp`."""
    mcp.add_tool(Tool.from_function(build_device_view, annotations=_ANNOTATIONS))
