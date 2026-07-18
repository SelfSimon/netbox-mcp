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
  and by whom. A shared service account (`svc-netbox-mcp`, see
  `scripts/create_service_account.py`) exists only as a fallback for local
  dev, tests, and CI.

Because it no longer needs the Django ORM, this server is a standalone
Python service — it does not need to run as a sidecar in the NetBox image.

## Repo structure

```
netbox-mcp/
├── src/netbox_mcp/   # server entry point (server.py) + auth pass-through (auth.py)
├── client/           # REST data client (rest.py) + branch helpers (branches.py)
├── schemas/          # Pydantic schemas + copied NetBox enums
├── tools/            # read and write MCP tools (planned)
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

`NETBOX_API_TOKEN` in `.env` is the local dev fallback (service account),
used when no per-request `Authorization` header is present — see
`src/netbox_mcp/auth.py`.

## Tests

```sh
pip install -e ".[dev]"
pytest -m "not integration"   # fast, needs neither Docker nor a NetBox instance
pytest -m integration         # requires a real running NetBox instance
                               # (with netbox_branching installed) + NETBOX_URL/
                               # NETBOX_API_TOKEN in the environment;
                               # otherwise tests are skipped.
```

## Building the image

```sh
docker build -t netbox-mcp:dev .
```

## CI/CD

A Git tag (`vX.Y.Z`) triggers the GitHub Actions CI
(`.github/workflows/build-publish.yml`), which builds the image and publishes
it to GHCR. The server deployment then references the published tag.

## Status

Data client implemented: REST-only, branch-first writes, per-user token
pass-through. Schemas and tools are still to be implemented.
