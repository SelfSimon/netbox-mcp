# CLAUDE.md

## Commands
- `pip install -e ".[dev]"` — install with dev deps
- `python -m netbox_mcp.server` — run the server locally (needs `.env`, see
  `.env.example`)
- `pytest -m "not integration"` — unit tests (what `ci.yml` runs)
- `ruff check .` — lint (the only linter CI enforces — `black`/`isort` are in
  `.pre-commit-config.yaml` but **not** run in CI, so local drift is possible)

## Architecture
- `client/registry.py` — NetBox object type → REST path (`ModelSpec`);
  `get_model_spec()` raises `KeyError` on unknown resource.
- `client/rest.py` — REST client; auto-paginates `list()`; maps HTTP errors
  to typed exceptions (`NetBoxConnectionError`/`PermissionError`/
  `NotFoundError`/`ValidationError`).
- `client/branches.py` — branch lifecycle helpers (create/get/list/
  `wait_until_ready`) — see Gotchas re: no merge.
- `schemas/` — Pydantic filter + write schemas, one set per covered object
  type; `choices.py` has hand-copied NetBox enums.
- `tools/read.py` / `tools/write.py` — MCP tool defs; writes always require
  a `branch` param routed via `X-NetBox-Branch`; reads always target `main`.
- `tools/generic.py` — `search_resources`/`get_resource`/`write_resource`,
  covering every resource in `client/registry.py` that has no dedicated
  tool; same `branch`/`main` rules as above.
- `src/netbox_mcp/auth.py` — per-request NetBox token pass-through
  (Starlette middleware + `ContextVar`), not full OAuth.

## Task tracking
- Track all work items in Jira, project key `NETBOX`, under epic `NETBOX-78`.

## Documentation
- **Dev/design docs** (architecture, design decisions, RFCs): Confluence,
  space `ADS`, under the page "Netbox/MCP" — not in this repo.
- **Product docs** (README, usage, coverage tracking, etc.): live in this
  repo; select files sync to Confluence via
  `.github/workflows/confluence-sync.yml`.
- To sync a markdown file, add this header at the very top:
  ```html
  <!--
  confluence-sync: true
  title: "Page Title"
  -->
  ```
  The workflow (triggers on push to `main`/`development` touching `**.md`)
  auto-discovers any file with `confluence-sync: true` and pushes it via
  `md2conf` under the `CONFLUENCE_ROOT_PAGE_ID` secret — no workflow edit
  needed to add or remove a synced doc.

## Relevant skills
- `mcp-server-dev:build-mcp-server` — this repo's core: developing an MCP
  server.
- `netbox-labs:netbox-api-integration` — the REST API integration patterns
  this server is built on.
- `netbox-labs:netbox-branching` — the branch-first write architecture
  (`X-NetBox-Branch`) used by every write tool.
- `netbox-labs:netbox-data-modeling` — extending `client/registry.py` and
  the schemas to new NetBox object types.

## Testing
- `pytest -m integration` needs `NETBOX_URL`/`NETBOX_API_TOKEN` as real
  process env vars — pytest does **not** auto-load `.env` (only
  `src/netbox_mcp/server.py` does, via `python-dotenv`, at server runtime).
  Export them first, e.g. `export $(grep -v '^#' .env | xargs)`.

## Gotchas
- `netbox_branching` branches are write-only from MCP: no `merge()`/`sync()`/
  `revert()`/`archive()` by design — merging into `main` is a human action in
  the NetBox UI. Do not add these.
- Only 5 of ~130 registered resources (site, device, interface, ip_address,
  vlan) have dedicated schemas + tools; everything else in
  `client/registry.py` is reachable generically via `tools/generic.py`
  (`search_resources`/`get_resource`/`write_resource` — no per-object
  Pydantic schema, NetBox's own REST API validates). Check
  `OBJECT_COVERAGE.md` before assuming a resource has a dedicated tool.
