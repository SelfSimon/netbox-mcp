# Releasing

How to cut a new `netbox-mcp` release. This covers the repo side only —
publishing the image to GHCR. Rolling that image out to Distriq's server
(bumping the tag in `netbox-custom-config` and redeploying) is documented
in Confluence, not here.

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
