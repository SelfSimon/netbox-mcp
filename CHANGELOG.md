# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Added

- Initial skeleton: FastMCP server entry point (`src/netbox_mcp/server.py`),
  standalone Dockerfile, CI/CD workflows (`ci.yml`, `build-publish.yml`),
  dev tooling (pre-commit, ruff, black, isort).
- Per-user token pass-through authentication (`src/netbox_mcp/auth.py`):
  `TokenCaptureMiddleware` captures each request's `Authorization` header
  into a contextvar so every MCP write is attributed to the calling user's
  own NetBox account, not a shared service account. Falls back to
  `NETBOX_API_TOKEN` when no per-request token is present (local dev,
  tests, CI).
- Data client: 100% REST API client (`client/rest.py`) — no
  Django ORM, no dependency on NetBox's source tree. `list()`/`get()`/`count()`
  for reads (with automatic pagination), `create()`/`update()`/`patch()`/`delete()`
  for writes. Branch-first writes via the `X-NetBox-Branch` header
  (`client/branches.py`: `create_branch`, `get_branch`, `list_branches`,
  `wait_until_ready` — deliberately no `merge()`/`sync()`/`revert()`/`archive()`,
  which stay human-only actions taken from the NetBox UI). `delete()` refuses
  to run without an active branch (`NetBoxNoBranchError`), so nothing
  destructive ever reaches `main` without a human merge review. Resource
  registry (`client/registry.py`, DCIM + IPAM scope) and typed exceptions
  (`client/exceptions.py`) mapped from NetBox's HTTP responses.
- `scripts/create_service_account.py`: provisions the `svc-netbox-mcp`
  fallback service account (DCIM/IPAM view/add/change/delete,
  `netbox_branching` view_branch/add_branch only — never merge/sync/revert/archive)
  used by integration tests, CI, and local dev when no per-user token is
  wired up yet.
- Pydantic schemas: NetBox `ChoiceSet` enums copied from NetBox
  4.6 (`schemas/choices.py` — site/device/IP address/VLAN status), read
  filter schemas per resource (`schemas/filters.py`), and write payload
  schemas for device/interface create-update and IP address assignment
  (`schemas/writes.py`), ready to back the read/write tools.
- Unit test suite (mocked NetBox, no network) covering config, registry,
  exceptions, auth, the REST client, branch helpers, and the new schemas.
  Integration test suite (`tests/integration/`) exercising the same
  surface against a real NetBox instance, skipped automatically when
  `NETBOX_URL`/`NETBOX_API_TOKEN` aren't set.

### Changed

- Clarified project scope: the goal is full NetBox object coverage through
  MCP (DCIM, IPAM, virtualization, circuits, tenancy, extras, ...), not a
  permanent DCIM + IPAM limit. Access control is left to NetBox's own
  per-user object permissions (via the pass-through token) rather than an
  allow-list in the MCP server itself; `client/registry.py`'s current
  DCIM + IPAM mapping is a first slice, extended as more tools are added.
- Dropped the original ORM-based read path in favor of 100% REST: the
  Django ORM didn't save code over the REST API's own FilterSets/serializers/
  permissions, added a sidecar deployment constraint, and had a latent
  permission bug (`.all()` instead of `.restrict(user, action)`). See the
  "Architecture" and "Décisions de cadrage" documentation for the full
  rationale.
