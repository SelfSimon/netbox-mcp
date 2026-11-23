import json
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from client.config import ClientSettings
from client.rest import BRANCH_HEADER, NetBoxRestClient
from tools import device_view
from tools.device_view_layout import (
    MAX_COLUMNS,
    LayoutBand,
    LayoutError,
    LayoutSection,
    Port,
    build_layout,
    derive_interface_stylename,
    derive_port_stylename,
    ports_from_templates,
)

# -- Stylenames --------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "stylename"),
    [
        ("GigabitEthernet1/0/1", "gigabitethernet0-1"),
        ("GigabitEthernet0/1", "gigabitethernet-1"),
        ("port1", "port-1"),
        ("port-1", "port--1"),
        ("eth0", "eth-0"),
        ("1", "p1"),
        ("mgmt", "mgmt"),
        ("ha", "ha"),
        ("xe-0/0/1", "xe-0-1"),
        ("Ethernet1/49/1", "ethernet49-1"),
        ("SFP+ 1", "sfp--1"),
    ],
)
def test_interface_stylename_matches_the_plugin(name, stylename):
    assert derive_interface_stylename(name) == stylename


@pytest.mark.parametrize(
    ("name", "stylename"),
    [("1", "p1"), ("Console", "console"), ("Port 1", "port-1"), ("1.1", "1.1")],
)
def test_port_stylename_matches_the_plugin(name, stylename):
    assert derive_port_stylename(name) == stylename


def test_ports_from_templates_skips_virtual_and_lag_in_plugin_kind_order():
    ports = ports_from_templates(
        {
            "interface": [
                {"name": "port1", "type": {"value": "1000base-t"}},
                {"name": "port2", "type": {"value": "1000base-t"}},
                {"name": "vlan1", "type": {"value": "virtual"}},
                {"name": "ae1", "type": {"value": "lag"}},
            ],
            "console_port": [{"name": "Console", "type": {"value": "rj-45"}}],
            "rear_port": [{"name": "1", "type": {"value": "8p8c"}}],
            "front_port": [{"name": "1", "type": {"value": "8p8c"}}],
        }
    )

    assert [(p.name, p.kind, p.stylename) for p in ports] == [
        ("port1", "interface", "port-1"),
        ("port2", "interface", "port-2"),
        ("Console", "console_port", "console"),
        ("1", "front_port", "p1"),
        ("1", "rear_port", "p1"),
    ]


# -- Layout ------------------------------------------------------------------


def _ports(*names: str) -> list[Port]:
    return [Port(n, "interface", derive_interface_stylename(n)) for n in names]


def _sections(*sections: dict) -> list[LayoutBand]:
    return [LayoutBand(rows=2, sections=[LayoutSection(**s) for s in sections])]


SWITCH = _ports(*(f"port{i}" for i in range(1, 9)), "mgmt", "ha")


def test_top_odd_switch_with_blanks_and_spacer():
    layout = build_layout(
        SWITCH,
        _sections(
            {"blank": 2},
            {"ports": ["ha", "mgmt"]},
            {"spacer": 1},
            {"ports": ["port1-8"]},
            {"blank": 1},
        ),
        2,
    )

    assert [" ".join(line) for line in layout.grid] == [
        "x x ha . port-1 port-3 port-5 port-7 z",
        "x x mgmt . port-2 port-4 port-6 port-8 z",
    ]
    assert layout.css == (
        ".deviceview.area {\n\tgrid-template-areas:\n"
        '  "x x ha . port-1 port-3 port-5 port-7 z"\n'
        '  "x x mgmt . port-2 port-4 port-6 port-8 z";\n}'
    )
    assert layout.unplaced == []
    assert layout.warnings == []


def test_top_even_row_major_and_all_patterns():
    ports = _ports(*(f"port{i}" for i in range(1, 5)))

    top_even = build_layout(
        ports, _sections({"ports": ["port1-4"], "pattern": "top-even"}), 2
    )
    row_major = build_layout(
        ports, _sections({"ports": ["port1-4"], "pattern": "row-major"}), 2
    )
    all_bottom = build_layout(
        ports, _sections({"ports": ["port1-4"], "pattern": "all", "row": 2}), 2
    )

    assert top_even.grid == [["port-2", "port-4"], ["port-1", "port-3"]]
    assert row_major.grid == [["port-1", "port-2"], ["port-3", "port-4"]]
    assert all_bottom.grid == [
        [".", ".", ".", "."],
        ["port-1", "port-2", "port-3", "port-4"],
    ]


def test_odd_count_leaves_an_empty_cell():
    layout = build_layout(
        _ports("port1", "port2", "port3"), _sections({"ports": ["port1-3"]}), 2
    )

    assert layout.grid == [["port-1", "port-3"], ["port-2", "."]]


def test_ranges_with_repeated_prefix_zero_padding_and_slashes():
    ports = _ports("Gi1/0/1", "Gi1/0/2", "Port01", "Port02")

    layout = build_layout(
        ports,
        _sections({"ports": ["Gi1/0/1-2"]}, {"ports": ["Port01-Port02"]}),
        2,
    )

    assert layout.grid == [["gi0-1", "port-01"], ["gi0-2", "port-02"]]


def test_names_are_matched_case_insensitively():
    layout = build_layout(
        _ports("Port1", "Port2"), _sections({"ports": ["port1-2"]}), 2
    )

    assert len(layout.placed) == 2


def test_unknown_duplicate_and_missing_range_ports_are_all_reported():
    with pytest.raises(LayoutError) as exc:
        build_layout(
            _ports("port1", "port2"),
            _sections({"ports": ["port1", "port1", "nope", "port1-4"]}),
            2,
        )

    errors = "\n".join(exc.value.errors)
    assert "unknown port 'nope'" in errors
    assert "'port3', 'port4'" in errors
    assert "'port1' is placed 3 times" in errors


def test_an_ambiguous_name_needs_a_kind():
    ports = [
        Port("Console", "interface", "console"),
        Port("Console", "console_port", "console"),
    ]

    with pytest.raises(LayoutError, match="set the section's `kind`"):
        build_layout(ports, _sections({"ports": ["Console"]}), 2)

    layout = build_layout(
        ports,
        _sections({"ports": ["Console"], "kind": "console_port", "pattern": "all"}),
        2,
    )
    assert layout.placed == [ports[1]]
    assert layout.collisions == {"console": ports}
    assert any("on top of each other" in w for w in layout.warnings)
    assert layout.unplaced == [ports[0]]


def test_a_stylename_css_cannot_use_is_refused():
    ports = [Port("1.1", "front_port", "1.1")]

    with pytest.raises(LayoutError, match="CSS cannot use"):
        build_layout(ports, _sections({"ports": ["1.1"], "pattern": "all"}), 2)


def test_rows_must_add_up_to_the_device_height():
    with pytest.raises(LayoutError, match="needs 4 "):
        build_layout(SWITCH, _sections({"ports": ["port1-8"]}), 4)


def test_a_huge_range_is_refused_without_expanding_it():
    with pytest.raises(LayoutError, match="spans more than"):
        build_layout(SWITCH, _sections({"ports": ["port1-999999999"]}), 2)


def test_repeated_ranges_stop_expanding_past_the_bound():
    with pytest.raises(ValidationError):
        LayoutSection(ports=["port1-8"] * (MAX_COLUMNS + 1))

    sections = [{"ports": ["port1-8"] * 100} for _ in range(10)]
    with pytest.raises(LayoutError, match=f"names more than {MAX_COLUMNS} ports"):
        build_layout(SWITCH, _sections(*sections), 2)


def test_spacers_and_blanks_are_bounded():
    with pytest.raises(ValidationError):
        LayoutSection(spacer=MAX_COLUMNS + 1)
    with pytest.raises(LayoutError, match="spacers and blanks span"):
        build_layout(
            SWITCH, _sections({"spacer": MAX_COLUMNS}, {"blank": MAX_COLUMNS}), 2
        )


def test_bands_stack_and_a_narrower_band_is_padded():
    ports = _ports(*(f"port{i}" for i in range(1, 7)))
    bands = [
        LayoutBand(rows=2, sections=[LayoutSection(ports=["port1-4"])]),
        LayoutBand(rows=2, sections=[LayoutSection(ports=["port5-6"])]),
    ]

    layout = build_layout(ports, bands, 4)

    assert layout.grid == [
        ["port-1", "port-3"],
        ["port-2", "port-4"],
        ["port-5", "x"],
        ["port-6", "x"],
    ]
    assert "padded" in layout.warnings[0]


def test_blank_names_never_reuse_a_stylename():
    ports = [Port("x", "front_port", "x"), Port("z", "front_port", "z")]

    layout = build_layout(
        ports,
        _sections({"blank": 1}, {"ports": ["x", "z"]}, {"blank": 1}),
        2,
    )

    assert layout.grid == [["y", "x", "w"], ["y", "z", "w"]]


def test_unplaced_ports_are_reported():
    layout = build_layout(SWITCH, _sections({"ports": ["port1-8"]}), 2)

    assert [p.name for p in layout.unplaced] == ["mgmt", "ha"]


def test_a_section_holds_exactly_one_content():
    with pytest.raises(ValidationError, match="exactly one"):
        LayoutSection(ports=["port1"], spacer=1)
    with pytest.raises(ValidationError, match="exactly one"):
        LayoutSection()


# -- Tool --------------------------------------------------------------------


def _netbox(requests, existing_view=None):
    templates = {
        "interface-templates": [
            {"name": f"port{i}", "type": {"value": "1000base-t"}} for i in range(1, 5)
        ],
        "console-port-templates": [{"name": "Console", "type": {"value": "rj-45"}}],
        "front-port-templates": [],
        "rear-port-templates": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/dcim/device-types/7/"):
            return httpx.Response(
                200, json={"id": 7, "display": "Acme S4", "u_height": 1.0}
            )
        for segment, results in templates.items():
            if f"/dcim/{segment}/" in path:
                assert parse_qs(request.url.query.decode())["device_type_id"] == ["7"]
                return httpx.Response(
                    200, json={"count": len(results), "next": None, "results": results}
                )
        if path.endswith("/device-view/") and request.method == "GET":
            # The plugin ignores filters: every view comes back, including
            # other device types' ones.
            views = [{"id": 1, "device_type": 2, "yaml_layout": ""}]
            views += [existing_view] if existing_view else []
            return httpx.Response(200, json={"count": len(views), "results": views})
        if request.method in ("POST", "PATCH"):
            body = json.loads(request.content)
            return httpx.Response(
                201, json={"id": 3, "url": "u", "display": "Acme S4", **body}
            )
        raise AssertionError(f"unexpected request {request.method} {path}")

    def make_client(branch=None):
        settings = ClientSettings(
            netbox_url="http://netbox.local", netbox_api_token="token123"
        )
        client = NetBoxRestClient(settings, branch=branch)
        client._client = httpx.Client(
            base_url="http://netbox.local/api/",
            headers=client._client.headers,
            transport=httpx.MockTransport(handler),
        )
        return client

    return make_client


SECTIONS = [
    LayoutSection(ports=["port1-4"]),
    LayoutSection(spacer=1),
    LayoutSection(ports=["Console"], pattern="all"),
]


def test_tool_refuses_without_a_description_and_lists_the_ports(monkeypatch):
    monkeypatch.setattr(device_view, "_client", _netbox([]))

    with pytest.raises(ValueError, match="never guesses") as exc:
        device_view.build_device_view(7)

    assert "port1 (interface)" in str(exc.value)
    assert "Console (console_port)" in str(exc.value)


def test_tool_dry_run_returns_the_grid_without_writing(monkeypatch):
    requests = []
    monkeypatch.setattr(device_view, "_client", _netbox(requests))

    result = device_view.build_device_view(7, sections=SECTIONS)

    assert result["grid"] == ["port-1 port-3 . console", "port-2 port-4 . ."]
    assert result["rows"] == 2
    assert result["placed"] == 5
    assert result["unplaced"] == []
    assert result["dry_run"] is True
    assert all(r.method == "GET" for r in requests)


def test_tool_write_needs_a_branch(monkeypatch):
    monkeypatch.setattr(device_view, "_client", _netbox([]))

    with pytest.raises(ValueError, match="pass `branch`"):
        device_view.build_device_view(7, sections=SECTIONS, dry_run=False)


def test_tool_creates_the_device_view_and_leaves_other_types_alone(monkeypatch):
    requests = []
    monkeypatch.setattr(device_view, "_client", _netbox(requests))

    result = device_view.build_device_view(
        7, sections=SECTIONS, branch="br123456", dry_run=False
    )

    post = requests[-1]
    assert post.method == "POST"
    assert post.headers[BRANCH_HEADER] == "br123456"
    body = json.loads(post.content)
    assert body["device_type"] == 7
    assert body["grid_template_area"] == result["grid_template_area"]
    assert result["action"] == "created"
    assert result["device_view"] == {"id": 3, "url": "u", "display": "Acme S4"}


def test_tool_patches_an_existing_view_and_warns_about_yaml(monkeypatch):
    requests = []
    existing = {"id": 9, "device_type": 7, "yaml_layout": "version: 1"}
    monkeypatch.setattr(device_view, "_client", _netbox(requests, existing))

    result = device_view.build_device_view(
        7, sections=SECTIONS, branch="br123456", dry_run=False
    )

    patch = requests[-1]
    assert patch.method == "PATCH"
    assert patch.url.path.endswith("/device-view/9/")
    assert set(json.loads(patch.content)) == {"grid_template_area"}
    assert result["action"] == "patched"
    assert any("yaml_layout" in w for w in result["warnings"])
