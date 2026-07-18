"""`netbox_branching` branch lifecycle helpers — creation and readiness only.

Deliberately absent: merge(), sync(), revert(), archive(). Those actions
apply branch changes to `main` (or discard them) and are gated by NetBox
permissions (`netbox_branching.merge_branch` and friends) that no MCP-used
account is ever granted. They are human actions performed from the NetBox
UI after reviewing the branch's diff — this module only lets the client
create the branch it will write into and wait for it to become usable.

Branch creation is asynchronous on the NetBox side: a new branch starts as
`NEW`, goes through `PROVISIONING`, and only accepts scoped requests once
`READY`. `wait_until_ready()` polls for that.
"""

from __future__ import annotations

import time
from typing import Any

from .exceptions import NetBoxClientError
from .rest import NetBoxRestClient

_BRANCHES_PATH = "plugins/branching/branches/"

_READY = "ready"
_FAILED = "failed"


def create_branch(
    client: NetBoxRestClient, name: str, description: str = ""
) -> dict[str, Any]:
    """Create a new branch. Requires `netbox_branching.add_branch`.

    Returns the branch as created (status will be "new" or "provisioning",
    not yet usable for scoped requests — pass the result to
    `wait_until_ready()` before writing into it).
    """
    response = client._request(
        "POST", _BRANCHES_PATH, json={"name": name, "description": description}
    )
    return response.json()


def get_branch(client: NetBoxRestClient, branch_id: int) -> dict[str, Any]:
    response = client._request("GET", f"{_BRANCHES_PATH}{branch_id}/")
    return response.json()


def list_branches(
    client: NetBoxRestClient, filters: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    response = client._request("GET", _BRANCHES_PATH, params=filters)
    payload = response.json()
    results.extend(payload["results"])
    next_url = payload.get("next")
    while next_url:
        response = client._request("GET", next_url)
        payload = response.json()
        results.extend(payload["results"])
        next_url = payload.get("next")
    return results


def wait_until_ready(
    client: NetBoxRestClient,
    branch_id: int,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> dict[str, Any]:
    """Poll a branch until its status is "ready".

    Raises NetBoxClientError if the branch reaches "failed" or if `timeout`
    seconds elapse first.
    """
    deadline = time.monotonic() + timeout
    branch = get_branch(client, branch_id)

    while branch["status"]["value"] != _READY:
        if branch["status"]["value"] == _FAILED:
            raise NetBoxClientError(f"Branch {branch_id} provisioning failed")
        if time.monotonic() >= deadline:
            raise NetBoxClientError(
                f"Branch {branch_id} did not become ready within {timeout}s "
                f"(status: {branch['status']['value']})"
            )
        time.sleep(poll_interval)
        branch = get_branch(client, branch_id)

    return branch
