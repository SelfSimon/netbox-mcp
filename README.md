# netbox-mcp

MCP (Model Context Protocol) server giving Claude read and write access to
NetBox — network and IT infrastructure automation.

## Approach

- **100% REST API**, read and write — no direct Django ORM access, no
  dependency on NetBox's source tree. NetBox's own FilterSets, serializers,
  object permissions, changelog, and webhooks apply identically to every
  request.
- **Branch-first writes**: every write goes through a `netbox_branching`
  branch (`X-NetBox-Branch` header), never directly against `main`.
  Deletes are allowed, but only inside a branch. Merging a branch into
  `main` is a human action taken from the NetBox UI — this client
  deliberately implements no `merge()`/`sync()`/`revert()`/`archive()`.
- **Per-user authentication (pass-through)**: MCP writes are made using the
  calling user's own NetBox API token, not a shared service account, so
  they're attributed to a real NetBox user. The branch's native `owner` and
  `BranchEvent` history give full traceability of what was changed via MCP
  and by whom. There is no service-account fallback: a request without an
  `Authorization` header gets `401`.
- **Full object coverage, no MCP-side allow-list**: the goal is for every
  NetBox object type reachable over the REST API — DCIM, IPAM,
  virtualization, circuits, tenancy, extras, and so on — to be usable
  through MCP, not just an initial subset. What a given caller can actually
  do is bounded by NetBox's own per-user object permissions (via the
  pass-through token above), not by a restriction baked into this server.
  `client/registry.py` today maps only a first slice of resources
  (DCIM + IPAM); widening it, plus the matching schemas and tools, to the
  rest of the NetBox data model is ongoing work, not a permanent scope
  decision.

Because it no longer needs the Django ORM, this server is a standalone
Python service — it does not need to run as a sidecar in the NetBox image.

## Repo structure

```
netbox-mcp/
├── src/netbox_mcp/   # server entry point (server.py) + auth pass-through (auth.py)
├── client/           # REST data client (rest.py) + branch helpers (branches.py)
├── schemas/          # Pydantic schemas + copied NetBox enums
├── tools/            # read, write and generic MCP tools + result shaping (response.py)
├── Dockerfile         # standalone Python image
├── requirements.txt
└── .env.example
```

## Local development

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in local values
```

The server holds no NetBox token of its own: MCP clients must send their
user's NetBox API token as `Authorization: Bearer <token>` (or `Token
<token>`), otherwise the request is rejected with `401` — see
`src/netbox_mcp/auth.py`.

## Tests

```sh
pip install -e ".[dev]"
pytest -m "not integration"   # fast, needs neither Docker nor a NetBox instance
pytest -m integration         # requires a real running NetBox instance
                               # (with netbox_branching installed) + NETBOX_URL/
                               # NETBOX_TEST_TOKEN (a personal token) in the
                               # environment;
                               # otherwise tests are skipped.
```

## Building the image

```sh
docker build -t netbox-mcp:dev .
```

## CI/CD

A Git tag (`vX.Y.Z`) triggers the GitHub Actions CI
(`.github/workflows/build-publish.yml`), which builds the image and publishes
it to GHCR. The server deployment then references the published tag. See
[docs/RELEASING.md](https://github.com/SelfSimon/netbox-mcp/blob/main/docs/RELEASING.md)
for the full release procedure.

## Status

Data client and schemas implemented: REST-only, branch-first writes,
per-user token pass-through, Pydantic filter/payload schemas + copied
NetBox choices in `schemas/`. Dedicated read tools are implemented for
site, device, interface, ip_address, and vlan (`list_*`/`get_*` in
`tools/read.py`, registered on the MCP server in
`src/netbox_mcp/server.py`). Dedicated write tools are implemented for
device and interface create/update, IP address assignment, and
`netbox_branching` branch create/list (`tools/write.py`, same
registration point) — every create/update tool requires an active branch,
and merge stays a human-only action in the NetBox UI.

Every other NetBox object type registered in `client/registry.py`
(98 of its 103 resources, across DCIM, IPAM, virtualization, circuits, tenancy,
wireless, VPN, extras, and users/core) is reachable through four generic
tools instead of a dedicated one per object: `search_resources`,
`get_resource`, `get_resource_schema`, and `write_resource`
(`tools/generic.py`) — `get_resource_schema` discovers a resource's
required/optional fields and valid values before you call `write_resource`
on it. A resource only graduates to a dedicated tool once it's high-usage
enough to warrant a precise Pydantic schema and per-action MCP
annotations — see
[docs/OBJECT_COVERAGE.md](https://github.com/SelfSimon/netbox-mcp/blob/main/docs/OBJECT_COVERAGE.md)
for the object-by-object tracker and the "Approach" section above for the
rationale.

### Lists, paging and response size

Every tool that returns a list (`list_*`, `get_resource` without an
`object_id`, `search_resources`, `list_branches`) returns an envelope, never
a bare list:

```json
{"count": 4127, "returned": 50, "offset": 0, "truncated": true,
 "next_offset": 50, "results": [...]}
```

- `count` is the total matching in NetBox; `truncated` means there is more —
  call again with `offset=next_offset`.
- A list holds 50 objects by default and 1000 at most (`limit`). No tool
  ever walks a whole table.
- A result is also capped in size (`MCP_MAX_RESPONSE_BYTES`, default
  400 000 bytes) because MCP clients fail opaquely on results over ~1 MB. A
  list over the cap is cut short and carries a `hint`; a single object over
  the cap is an explicit error.
- To get more objects per call, ask for less of each one: `fields=["id",
  "name", ...]` returns only those fields, and `brief=True` returns NetBox's
  minimal representation — which leaves out custom fields, tags and related
  objects.
