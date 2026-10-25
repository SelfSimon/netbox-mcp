# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Changed

- `fastmcp` and `mcp` are bounded to one major version, `fastmcp>=4.1,<5`
  and `mcp>=2.3,<3`, in both `pyproject.toml` and `requirements.txt`
  (NETBOX-119). Local dev, CI and the image now install the same major
  version; the `0.1.0` image already shipped fastmcp 4.1.0 / mcp 2.3.0
  despite the FastMCP 3.x note below. A new major version now needs an
  explicit change in the repo.
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
