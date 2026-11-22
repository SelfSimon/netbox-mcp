# Releasing

How to cut a new `netbox-mcp` release. This covers the repo side only —
publishing the image to GHCR. Rolling that image out to Distriq's server
(bumping the tag in `netbox-custom-config` and redeploying) is documented
in Confluence, not here.

0. On `development`, run the whole test suite against the dev NetBox, with
   a personal token that may add and delete branches there:
   ```sh
   export $(grep -v '^#' .env | xargs)   # NETBOX_URL, NETBOX_TEST_TOKEN
   pytest -m "not integration"
   pytest -m integration
   ```
   Any failure blocks the release. `pytest -m integration` includes the
   reference journey
   ([tests/integration/test_journey.py](https://github.com/SelfSimon/netbox-mcp/blob/main/tests/integration/test_journey.py),
   NETBOX-148): a branch with an accented name, two device types with
   their interface templates, racked devices with tenant and owner,
   renamed templates, a device deleted then recreated, and the exact
   `get_branch_diff` of all that. A failure names the step and what
   differed. Its owner check skips unless an owner `netbox-mcp-test`
   exists in dev (owners are created in the NetBox UI). An `XPASS` means a
   feature tracked by an xfail (NETBOX-145, NETBOX-146) now works: turn
   it into a plain test. The session deletes every branch it created, so
   no test data stays in dev; run it against dev only, never prod.
1. Bump `version` in
   [pyproject.toml](https://github.com/SelfSimon/netbox-mcp/blob/main/pyproject.toml)
   to `X.Y.Z`.
2. In
   [docs/CHANGELOG.md](https://github.com/SelfSimon/netbox-mcp/blob/main/docs/CHANGELOG.md),
   rename the `## Unreleased` section to `## [X.Y.Z] - YYYY-MM-DD` and start
   a fresh empty `## Unreleased` section above it.
3. Commit, merge `development` into `main`.
4. Tag the merge commit and push the tag:
   ```sh
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. The tag push triggers
   [build-publish.yml](https://github.com/SelfSimon/netbox-mcp/blob/main/.github/workflows/build-publish.yml),
   which builds the image and pushes
   `ghcr.io/<owner>/netbox-mcp:X.Y.Z` and `ghcr.io/<owner>/netbox-mcp:latest`.

Note: `pyproject.toml`'s `version` field is not read by the release
workflow — the published image tag comes from the git tag name
(`GITHUB_REF_NAME`), not from `pyproject.toml`. Keep the two in sync
manually so `pip show netbox-mcp` and the published image tag agree.
