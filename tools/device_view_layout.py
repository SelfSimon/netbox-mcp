"""Pure layout logic behind build_device_view() (NETBOX-150).

netbox_device_view draws a device's ports from a CSS `grid-template-areas`
string: every port element gets `grid-area: <stylename>`, a name the plugin
derives from the port's name. Writing that string by hand means knowing
the exact stylename of every port and keeping each named area a rectangle,
with every grid row the same length — easy to get wrong, and the browser
silently drops the whole declaration on a single bad token.

This module builds the string from a description of the real front panel
(sections of ports, spacers and blanks, per band of rows) and the device
type's component templates. It never guesses a layout: no description, no
grid (the caller refuses). No I/O here — tools/device_view.py fetches the
templates and writes the result.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# -- Stylenames (copied from netbox_device_view/utils.py) -------------------

_INTERFACE_RE = re.compile(
    r"^(?P<type>([a-zA-Z\-_]*))(\/|(?P<dev>[0-9]+).|\s)?((?P<module>[0-9]+).|\s)?"
    r"((?P<port>[0-9]+))$"
)


def derive_interface_stylename(name: str) -> str:
    """The plugin's `_derive_interface_stylename()`, kept byte-identical."""
    matches = _INTERFACE_RE.search(name.lower())
    if matches:
        if not matches["type"]:
            stylename = matches["port"]
        else:
            stylename = (
                matches["type"] + (matches["module"] or "") + "-" + matches["port"]
            )
    else:
        stylename = re.sub(r"[^.a-zA-Z\d]", "-", name.lower())
    if stylename.isdigit():
        stylename = f"p{stylename}"
    return stylename


def derive_port_stylename(name: str) -> str:
    """The plugin's `_derive_port_stylename()` (console/front/rear ports)."""
    stylename = re.sub(r"[^.a-zA-Z\d]", "-", name.lower())
    if stylename.isdigit():
        stylename = f"p{stylename}"
    return stylename


PortKind = Literal["interface", "console_port", "front_port", "rear_port"]

# Component template resource per kind, in the plugin's order.
TEMPLATE_RESOURCES: dict[PortKind, str] = {
    "interface": "interface_template",
    "console_port": "console_port_template",
    "front_port": "front_port_template",
    "rear_port": "rear_port_template",
}

# Interface types the plugin never draws.
_SKIPPED_INTERFACE_TYPES = {"virtual", "lag"}

# A name the browser accepts both as a `grid-template-areas` cell and as a
# `grid-area` value (ASCII subset of a CSS custom-ident). A "." splits a
# cell in two, and a leading digit is not an ident: either one leaves the
# port outside the grid.
_CSS_AREA_NAME_RE = re.compile(r"-?[A-Za-z_][A-Za-z0-9_-]*|--[A-Za-z0-9_-]*")


@dataclass(frozen=True)
class Port:
    """A drawable component template of the device type."""

    name: str
    kind: PortKind
    stylename: str


def _type_value(template: dict[str, Any]) -> str:
    value = template.get("type")
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value or "")


def ports_from_templates(templates: dict[PortKind, list[dict[str, Any]]]) -> list[Port]:
    """The ports the plugin draws for a device type, in its order: interface
    templates (minus virtual and LAG), then console, front and rear port
    templates. Each list keeps the order it is given in: fetch it with
    `ordering=name`, NetBox's natural sort, which the plugin uses too."""
    ports: list[Port] = []
    for kind in TEMPLATE_RESOURCES:
        for template in templates.get(kind, []):
            if kind == "interface":
                if _type_value(template) in _SKIPPED_INTERFACE_TYPES:
                    continue
                stylename = derive_interface_stylename(template["name"])
            else:
                stylename = derive_port_stylename(template["name"])
            ports.append(Port(template["name"], kind, stylename))
    return ports


# -- Layout description ------------------------------------------------------

Pattern = Literal["top-odd", "top-even", "row-major", "all"]


# Widest grid a description may ask for. The widest real front panels
# (a 1U 96-port patch panel, a 2U 48-port switch) are well under 200
# columns; this bounds what a caller can make the server allocate.
MAX_COLUMNS = 512


class LayoutSection(BaseModel):
    """One block of columns, left to right, spanning every row of its band.

    Exactly one of `ports`, `spacer` or `blank`.
    """

    ports: list[str] | None = Field(
        default=None,
        description=(
            "Ports of this block, in order: template names (e.g. "
            '"GigabitEthernet1/0/1") or ranges "<prefix><start>-<end>" '
            '(e.g. "GigabitEthernet1/0/1-48", "Port1-Port24").'
        ),
    )
    pattern: Pattern = Field(
        default="top-odd",
        description=(
            "How the ports fill the block's rows: `top-odd` column by column, "
            "top to bottom (1 above 2, 3 above 4 — the usual switch); "
            "`top-even` column by column, bottom to top (2 above 1); "
            "`row-major` row by row (1-24 on top, 25-48 below — a patch "
            "panel); `all` every port on the single row `row`."
        ),
    )
    row: int = Field(
        default=1,
        ge=1,
        description="Row of the band (1 = top) for pattern `all`.",
    )
    kind: PortKind | None = Field(
        default=None,
        description=(
            "Restrict `ports` to one kind of template when a name exists as "
            "several (e.g. an interface and a console port both named "
            '"Console").'
        ),
    )
    spacer: int | None = Field(
        default=None, ge=1, le=MAX_COLUMNS, description="Number of empty gap columns."
    )
    blank: int | None = Field(
        default=None,
        ge=1,
        le=MAX_COLUMNS,
        description=(
            "Number of filler columns: chassis surface with no port (the left "
            "or right margin of the front panel)."
        ),
    )

    @model_validator(mode="after")
    def _one_content(self) -> LayoutSection:
        given = [
            key
            for key in ("ports", "spacer", "blank")
            if getattr(self, key) is not None
        ]
        if len(given) != 1:
            raise ValueError(
                "a section holds exactly one of `ports`, `spacer` or `blank`"
                + (f" (got {', '.join(given)})" if given else "")
            )
        if self.ports is not None and not self.ports:
            raise ValueError("`ports` must name at least one port")
        return self


class LayoutBand(BaseModel):
    """A horizontal band of `rows` grid rows (2 rows per rack unit)."""

    rows: int = Field(ge=1, description="Grid rows in this band (2 per U).")
    sections: list[LayoutSection] = Field(min_length=1, max_length=MAX_COLUMNS)


# -- Building ----------------------------------------------------------------


class LayoutError(ValueError):
    """The description cannot produce a valid grid; `errors` lists why."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("invalid device view layout:\n- " + "\n- ".join(errors))


@dataclass
class Layout:
    grid: list[list[str]]
    css: str
    placed: list[Port]
    unplaced: list[Port]
    collisions: dict[str, list[Port]]
    warnings: list[str] = field(default_factory=list)


_RANGE_RE = re.compile(r"^(?P<prefix>.*?)(?P<start>\d+)-(?P=prefix)?(?P<end>\d+)$")

_BLANK_NAMES = ("x", "z", "y", "w")


def _filler_names(taken: set[str]):
    """Distinct filler area names, none of them a port's stylename."""
    for round_ in range(1000):
        for base in _BLANK_NAMES:
            name = base if round_ == 0 else f"{base}{round_ + 1}"
            if name not in taken:
                yield name


class _RangeTooLongError(Exception):
    """A range names more ports than the device type has."""


class _Resolver:
    """Turns the names and ranges of a section into ports."""

    def __init__(self, ports: list[Port]) -> None:
        # A range longer than this can't be a typo for real ports.
        self._max_range = max(len(ports), MAX_COLUMNS)
        self._exact: dict[str, list[Port]] = defaultdict(list)
        self._folded: dict[str, list[Port]] = defaultdict(list)
        for port in ports:
            self._exact[port.name].append(port)
            self._folded[port.name.lower()].append(port)

    def _lookup(self, name: str, kind: PortKind | None) -> list[Port]:
        found = self._exact.get(name) or self._folded.get(name.lower()) or []
        if kind is not None:
            found = [port for port in found if port.kind == kind]
        return found

    def _expand(self, ref: str, kind: PortKind | None) -> list[str] | None:
        if self._lookup(ref, kind):
            return [ref]
        match = _RANGE_RE.match(ref)
        if not match:
            return None
        start, end = match["start"], match["end"]
        width = len(start) if start.startswith("0") else 0
        if abs(int(end) - int(start)) + 1 > self._max_range:
            raise _RangeTooLongError
        step = 1 if int(end) >= int(start) else -1
        return [
            f"{match['prefix']}{str(n).zfill(width)}"
            for n in range(int(start), int(end) + step, step)
        ]

    def resolve(
        self, refs: list[str], kind: PortKind | None, errors: list[str]
    ) -> list[Port]:
        resolved: list[Port] = []
        for ref in refs:
            try:
                names = self._expand(ref.strip(), kind)
            except _RangeTooLongError:
                errors.append(
                    f"{ref!r} spans more than {self._max_range} ports: the device "
                    "type cannot have that many"
                )
                continue
            if names is None:
                errors.append(f"unknown port {ref!r}")
                continue
            missing = []
            for name in names:
                found = self._lookup(name, kind)
                if not found:
                    missing.append(name)
                elif len(found) > 1:
                    kinds = ", ".join(sorted(port.kind for port in found))
                    errors.append(
                        f"port {name!r} exists as several templates ({kinds}): "
                        "set the section's `kind`"
                    )
                else:
                    resolved.append(found[0])
            if missing:
                shown = ", ".join(repr(name) for name in missing[:5])
                more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
                errors.append(f"{ref!r}: no port template named {shown}{more}")
        return resolved


def _fill(ports: list[Port], pattern: Pattern, rows: int, row: int) -> list[list[str]]:
    """The cells of a port block: `rows` lists of the same length."""
    names = [port.stylename for port in ports]
    if pattern == "all":
        block = [["."] * len(names) for _ in range(rows)]
        block[row - 1] = names
        return block
    cols = math.ceil(len(names) / rows)
    block = [["."] * cols for _ in range(rows)]
    for index, name in enumerate(names):
        if pattern == "row-major":
            r, c = divmod(index, cols)
        else:
            c, r = divmod(index, rows)
            if pattern == "top-even":
                r = rows - 1 - r
        block[r][c] = name
    return block


def _non_rectangular(grid: list[list[str]]) -> list[str]:
    cells: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for r, line in enumerate(grid):
        for c, name in enumerate(line):
            if name != ".":
                cells[name].append((r, c))
    bad = []
    for name, positions in cells.items():
        rows = [r for r, _ in positions]
        cols = [c for _, c in positions]
        height = max(rows) - min(rows) + 1
        width = max(cols) - min(cols) + 1
        if height * width != len(positions):
            bad.append(name)
    return bad


def render_css(grid: list[list[str]]) -> str:
    """The `grid_template_area` text, in the format of the existing views."""
    lines = [f'  "{" ".join(line)}"' for line in grid]
    return ".deviceview.area {\n\tgrid-template-areas:\n" + "\n".join(lines) + ";\n}"


def build_layout(ports: list[Port], bands: list[LayoutBand], total_rows: int) -> Layout:
    """Build the grid described by `bands` from the device type's `ports`.

    Raises LayoutError listing every problem found: unknown or ambiguous
    ports, a port placed twice, a stylename the browser cannot use, bands
    that do not add up to the device's rows, or an area that is not a
    rectangle.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Both checked before any grid is allocated: the rows then come from
    # the device type's height, and the columns are bounded.
    band_rows = sum(band.rows for band in bands)
    if band_rows != total_rows:
        message = (
            f"the bands hold {band_rows} rows but the device type needs "
            f"{total_rows} (2 per U)"
        )
        raise LayoutError([message])
    for b, band in enumerate(bands, start=1):
        fixed = sum(
            (section.spacer or 0) + (section.blank or 0) for section in band.sections
        )
        if fixed > MAX_COLUMNS:
            message = (
                f"band {b}: its spacers and blanks span {fixed} columns, more "
                f"than the {MAX_COLUMNS} a grid may have"
            )
            raise LayoutError([message])

    resolver = _Resolver(ports)
    fillers = _filler_names({port.stylename for port in ports})
    placed: list[Port] = []
    seen: dict[Port, int] = {}
    band_grids: list[list[list[str]]] = []

    for b, band in enumerate(bands, start=1):
        grid: list[list[str]] = [[] for _ in range(band.rows)]
        for section in band.sections:
            if section.spacer is not None:
                block = [["."] * section.spacer for _ in range(band.rows)]
            elif section.blank is not None:
                name = next(fillers)
                block = [[name] * section.blank for _ in range(band.rows)]
            else:
                if section.pattern == "all" and section.row > band.rows:
                    errors.append(
                        f"band {b}: row {section.row} is outside its {band.rows} rows"
                    )
                    continue
                section_ports = resolver.resolve(
                    section.ports or [], section.kind, errors
                )
                for port in section_ports:
                    seen[port] = seen.get(port, 0) + 1
                    if seen[port] == 1:
                        placed.append(port)
                block = _fill(section_ports, section.pattern, band.rows, section.row)
            for line, cells in zip(grid, block, strict=True):
                line.extend(cells)
        band_grids.append(grid)

    for port, count in seen.items():
        if count > 1:
            errors.append(f"port {port.name!r} is placed {count} times")
    for port in placed:
        if not _CSS_AREA_NAME_RE.fullmatch(port.stylename):
            errors.append(
                f"port {port.name!r} has the stylename {port.stylename!r}, which "
                "CSS cannot use as a grid area: rename the port template, or "
                "leave it out of the layout"
            )

    width = max((len(grid[0]) for grid in band_grids if grid and grid[0]), default=0)
    if width == 0:
        errors.append("the layout has no column")
    full: list[list[str]] = []
    for b, grid in enumerate(band_grids, start=1):
        missing = width - len(grid[0])
        if missing:
            name = next(fillers)
            for line in grid:
                line.extend([name] * missing)
            warnings.append(
                f"band {b} was {missing} columns narrower than the widest band: "
                f"padded on the right with the blank {name!r}"
            )
        full.extend(grid)

    bad = _non_rectangular(full)
    if bad:
        errors.append(f"areas that are not rectangles: {', '.join(bad)}")
    if errors:
        raise LayoutError(errors)

    by_stylename: dict[str, list[Port]] = defaultdict(list)
    for port in ports:
        by_stylename[port.stylename].append(port)
    collisions = {name: group for name, group in by_stylename.items() if len(group) > 1}
    if collisions:
        warnings.append(
            "several ports share a stylename, so the plugin draws them on top "
            "of each other: " + ", ".join(sorted(collisions))
        )

    placed_set = set(placed)
    unplaced = [port for port in ports if port not in placed_set]
    if unplaced:
        warnings.append(
            f"{len(unplaced)} ports are not in the layout: the browser puts "
            "them after the grid, outside the front panel"
        )

    return Layout(
        grid=full,
        css=render_css(full),
        placed=placed,
        unplaced=unplaced,
        collisions=collisions,
        warnings=warnings,
    )
