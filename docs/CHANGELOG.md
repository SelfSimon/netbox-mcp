# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Fixed

- `create_branch` no longer hides a branch it created (NETBOX-147). When
  the branch is not ready in time, the error now gives its name and
  `schema_id`, says it exists, and tells the caller to reuse it instead of
  creating another. Names with an en-dash, `/`, accents or emoji work:
  that was not the cause of the `fetch failed` seen in prod.

### Changed

- Every NetBox error now gives its HTTP code and, when NetBox sends one,
  NetBox's own message (for example `permission denied by NetBox (403):
  ...`, `data rejected by NetBox (400): ...`). Non-JSON answers, such as a
  proxy's HTML page, are shortened.

## [0.3.1] - 2026-11-22

Nothing to change to deploy: same configuration as 0.3.0.

### Fixed

- `get_branch_diff` no longer lists an object created then deleted in the
  branch, and no longer counts it in `summary` (NETBOX-144).
  netbox_branching keeps such an object as a `create` with no data, which
  showed up as an empty `data: {}` entry. These objects end up neither in
  `main` nor in the branch, and the merge skips them. The tool now reads
  every change in the branch and filters by `object_type` and `action`
  itself, so `count` and `next_offset` only cover real changes.

## [0.3.0] - 2026-11-21

Nothing to change to deploy: same configuration as 0.2.0.

### Added

- `get_branch_diff` tool, read-only (NETBOX-104): what a branch changes
  compared with `main`, from netbox_branching's ChangeDiffs. One entry per
  changed object, grouped by object type: the new object's non-empty
  fields for a create, `{before, after}` for each altered field of an
  update, the object's identity for a delete, and the fields in conflict
  with `main`. Filters by `object_type` and `action`; a `summary` counts
  the branch's changes per action. Reads never see a branch, so this is
  how Claude checks its writes before handing the branch to a human.

## [0.2.0] - 2026-11-20

To deploy: set the optional `NETBOX_UI_URL` (NetBox's browser address)
next to `NETBOX_URL`, so refusals link to the right NetBox page.

### Added

- `list_devices` accepts the `rack_id` and `location_id` filters
  (NETBOX-140). `location_id` also matches devices in child locations,
  like NetBox's own filter.
- The 10 component templates (`dcim/*-templates/`: console port, console
  server port, power port, power outlet, interface, front port, rear port,
  module bay, device bay, inventory item) are in the registry, so the
  generic tools reach them (NETBOX-137). A device type gets its components
  once, and NetBox creates them on every new device of that type, also
  inside a branch.
- `owner` and `owner_group` (`users/owners/`, `users/owner-groups/`,
  NetBox 4.5+ ownership) are in the registry (NETBOX-138): an owner can be
  looked up by name before it is set on a device. The registry now holds
  115 resources.
- `create_device`/`update_device` accept `position` (half units allowed),
  `face`, `airflow`, `platform`, `cluster`, `owner`, `primary_ip4`,
  `primary_ip6`, `description` and `tags`; `create_interface`/
  `update_interface` accept `label`, `speed`, `duplex`, `mgmt_only`,
  `mark_connected`, `poe_mode`, `poe_type`, `mode`, `untagged_vlan`,
  `tagged_vlans`, `lag`, `parent`, `vrf` and `tags` (NETBOX-139). Choice
  fields are validated against NetBox 4.6's values; tags are objects,
  `{"name": ...}` or `{"slug": ...}`. Custom fields come later
  (NETBOX-141).

### Fixed

- Writes no longer reach `main` through resources netbox_branching does
  not version (NETBOX-142). The plugin ignores `X-NetBox-Branch` for
  models without change logging or exempted by it, so an `owner` created
  "in a branch" landed directly on main. The 19 such resources (`user`,
  `group`, `permission`, `token`, `owner`, `owner_group`, `custom_field`,
  `custom_field_choice_set`, `custom_link`, `export_template`,
  `saved_filter`, `bookmark`, `script`, `webhook`, `event_rule`,
  `notification_group`, `data_source`, `data_file`, `job`) are marked
  `branchable=False` in the registry: the client refuses every write to
  them before any request, `write_resource` and `get_resource_schema`
  say to create or change them in the NetBox UI, and `search_resources`
  returns `writable: false`. Reads are unchanged. An integration test
  checks the list against the live `branching` object-type feature.
  The refusal links to the NetBox page only when the optional
  `NETBOX_UI_URL` (NetBox's browser address) is set, otherwise it gives
  the page path: `NETBOX_URL` is often internal (`http://netbox:8080` in
  Docker) and is never used for links.
- `get_resource_schema` exposes the fields of inline nested objects
  instead of an empty `reference_by` (NETBOX-137). Front/rear port
  mappings (`rear_ports` / `front_ports`, NetBox 4.5+) and cable
  `a_terminations` / `b_terminations` now show the expected shape, e.g.
  `[{position, rear_port, rear_port_position}]`.

### Changed

- `fastmcp` and `mcp` are bounded to one major version, `fastmcp>=4.1,<5`
  and `mcp>=2.3,<3`, in both `pyproject.toml` and `requirements.txt`
  (NETBOX-119). Local dev, CI and the image now install the same major
  version; the `0.1.0` image already shipped fastmcp 4.1.0 / mcp 2.3.0
  despite the FastMCP 3.x note below. A new major version now needs an
  explicit change in the repo.
- Dependabot (`.github/dependabot.yml`) opens weekly PRs against
  `development` for pip and GitHub Actions updates; minor and patch bumps
  are grouped, each major bump gets its own PR (NETBOX-119).
- Minimum versions raised by Dependabot: `fastmcp>=4.2.0,<5`,
  `uvicorn>=0.54.0`, `anyio>=4.16.0`; dev: `pytest>=9.2.0`,
  `pytest-mock>=3.17.0`, `pre-commit>=4.7.0`, `ruff==0.17.5`. GitHub
  Actions moved to `actions/checkout@v7`, `actions/setup-python@v7` and
  the v4/v7 Docker actions.
- CI also runs on pull requests to `development`, so Dependabot's PRs are
  tested. A unit test fails when the pre-commit ruff hook's `rev` differs
  from the `ruff==` pin, since Dependabot only bumps the latter.
- `ToolAnnotations` use the MCP SDK v2 field names (`read_only_hint`,
  `destructive_hint`, `idempotent_hint`); the wire format is unchanged.

## [0.1.0] - 2026-10-09

First release. It describes what the image ships, not the steps taken to
get there.

### Server and deployment

- FastMCP 3.x server over HTTP (`src/netbox_mcp/server.py`), packaged as a
  standalone Python image: no NetBox/Django source tree, no sidecar. The
  container only needs `NETBOX_URL`.
- Server `instructions` in `InitializeResult` (NETBOX-108): the rules that
  span several tools — the list envelope and how to page, `brief`/`fields`,
  one branch per task and human-only merge, dedicated vs generic tools,
  `get_resource_schema` before `write_resource`, `patch` vs `update`. Not
  every MCP client passes `instructions` on to the model, so the tool
  descriptions stay the source of truth.
- `build-publish.yml` builds the image and pushes it to GHCR on every
  `vX.Y.Z` tag; `ci.yml` runs `ruff check`, `ruff format --check` and the
  unit tests (NETBOX-118).

### Authentication

- Per-user token pass-through (`src/netbox_mcp/auth.py`):
  `TokenCaptureMiddleware` captures each request's `Authorization` header
  (`Bearer <token>` or `Token <token>`) into a contextvar, so every call is
  made — and every write is recorded in NetBox's changelog — as the calling
  user.
- No service account and no fallback (NETBOX-115): the server holds no
  token, and a request without one is answered `401` with
  `WWW-Authenticate` before it reaches a tool.

### Data client

- 100% REST client (`client/rest.py`), no Django ORM: `list()`/
  `list_page()`/`get()`/`count()`/`schema()` for reads, `create()`/
  `update()`/`patch()`/`delete()` for writes. NetBox's own FilterSets,
  serializers, object permissions, changelog and webhooks apply to every
  request.
- Lists are bounded in the client, not per tool (NETBOX-96, NETBOX-113):
  one request with `limit=50` by default, never more than 1000 objects (a
  missing, zero or larger `limit` is clamped), and pagination is followed
  only with an explicit `paginate=True`, which no tool uses.
- HTTP errors are mapped to typed exceptions (`client/exceptions.py`);
  NetBox's validation details (HTTP 400) are passed on as-is (NETBOX-95).
- Resource registry (`client/registry.py`): 103 NetBox object types across
  DCIM, IPAM, virtualization, circuits, tenancy, wireless, VPN, extras and
  users/core. Plugin objects are not registered — see
  `docs/OBJECT_COVERAGE.md` (NETBOX-117).

### Branch-first writes

- Every write goes to a `netbox_branching` branch through the
  `X-NetBox-Branch` header; nothing is ever written to `main` directly, and
  reads always target `main`.
- `client/branches.py` has `create_branch`, `get_branch`, `list_branches`
  and `wait_until_ready`, and deliberately no merge, sync, revert or
  archive: merging into `main` is a human action in the NetBox UI, whatever
  permissions the caller's token holds. A unit test checks their absence.
- `delete()` refuses to run without an active branch
  (`NetBoxNoBranchError`), before any request is sent.

### Tools

- Dedicated read tools (`tools/read.py`): `list_*`/`get_*` for site,
  device, interface, ip_address and vlan, with Pydantic filters
  (`schemas/filters.py`). Annotated `readOnlyHint`/`idempotentHint`.
- Dedicated write tools (`tools/write.py`): `create_device`/
  `update_device`, `create_interface`/`update_interface`,
  `assign_ip_address`, validated by Pydantic schemas (`schemas/writes.py`),
  plus `create_branch`/`list_branches`. Each write requires a `branch`. The
  docstrings tell callers to use one branch per task and to reuse it.
- Generic tools (`tools/generic.py`) for every registered resource with no
  dedicated tool (NETBOX-93): `search_resources`, `get_resource`,
  `write_resource`. No per-object schema; NetBox validates the payload.
  `write_resource(action="delete")` requires `confirm=True` (NETBOX-103).
- `get_resource_schema(resource)` (NETBOX-99/100/101): required and
  optional fields and enum choices, from DRF `OPTIONS`, with read-only
  fields dropped and related objects reduced to how to reference them.
  Meant to be called before `write_resource`.

### Lists, response size and field selection

- Every tool that returns a list — the five `list_*` tools, `get_resource`
  without an `object_id`, `search_resources` and `list_branches` — returns
  an envelope (NETBOX-113): `{count, returned, offset, truncated,
  next_offset, results}`, plus `hint` when the list was cut to fit the size
  cap. `count` is NetBox's total; when `truncated` is true, call again with
  `offset=next_offset`.
- No tool result can exceed the client's ~1 MB limit (NETBOX-116). A shared
  layer, `tools/response.py`, caps every result at `MCP_MAX_RESPONSE_BYTES`
  (default 400 000). FastMCP sends a dict result twice — as structured
  content and as JSON text embedded in a JSON string, where quotes and
  backslashes are escaped again — and the measure counts both copies, so a
  result stays under about 800 kB on the wire. A list over the cap is cut
  and says so; a single object over the cap raises an explicit error
  pointing to `fields`/`brief`; an oversized write result is reduced to
  `{id, url, display, truncated, hint}`, since the write itself succeeded.
- `brief` and `fields` on every read (NETBOX-114). `brief=True` asks NetBox
  for its minimal representation (id, url, display, name and a few key
  fields — **no custom fields, tags or related objects**); `fields=[...]`
  returns only the named fields. Both are plain NetBox query params, on
  every `list_*` filter, on the five `get_*` tools and on `get_resource`.
  `fields` was verified against NetBox 4.6.2.

### Tests

- Unit tests (mocked NetBox, no network) for config, registry, exceptions,
  auth, the REST client, branch helpers, schemas, every tool and the
  server.
- Integration tests (`tests/integration/`) against a real NetBox, verified
  on NetBox 4.6.2 with `netbox_branching` 1.0.3. They take a personal token
  from `NETBOX_TEST_TOKEN` and are skipped when it is not set.
