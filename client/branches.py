"""`netbox_branching` branch helpers — creation, readiness, and a read-only
view of a branch's changes (its diff against main, for human review).

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

from .exceptions import NetBoxClientError, NetBoxNotFoundError, NetBoxValidationError
from .rest import NetBoxRestClient

_BRANCHES_PATH = "plugins/branching/branches/"
_CHANGES_PATH = "plugins/branching/changes/"

_READY = "ready"
_FAILED = "failed"

CHANGE_ACTIONS = ("create", "update", "delete")

# Bookkeeping fields every write touches: they are not part of what the
# branch changes, and would show up in every update.
_NOISE_FIELDS = frozenset({"created", "last_updated"})


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
) -> dict[str, Any]:
    """Return one bounded page of branches (see `NetBoxRestClient.list_page`)."""
    return client._page(_BRANCHES_PATH, filters)


def list_changes(
    client: NetBoxRestClient, schema_id: str, filters: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return one bounded page of the branch's ChangeDiffs, raw.

    netbox_branching keeps ONE ChangeDiff per object changed in the branch
    (not one per write): `original_data` is the object before the branch
    touched it (null for a create), `modified_data` its state in the branch
    (null for a delete), `current_data` its state in main now. Read from
    main, like every read: the endpoint is not branch-scoped.
    """
    try:
        return client._page(_CHANGES_PATH, {**(filters or {}), "branch": schema_id})
    except NetBoxValidationError as exc:
        # NetBox's own message ("Select a valid choice. x is not one of the
        # available choices.") does not say what to do about it.
        if "branch" not in exc.errors:
            raise
        raise NetBoxNotFoundError(
            f"No branch with schema_id {schema_id!r}: pass the `schema_id` "
            "of a branch from list_branches(), not its name or id."
        ) from exc


def count_changes(
    client: NetBoxRestClient, schema_id: str, filters: dict[str, Any] | None = None
) -> int:
    """Number of the branch's ChangeDiffs matching `filters`, in one request."""
    return list_changes(client, schema_id, {**(filters or {}), "limit": 1})["count"]


def _clean(data: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (data or {}).items() if k not in _NOISE_FIELDS}


def summarize_change(change: dict[str, Any]) -> dict[str, Any]:
    """Reduce a ChangeDiff to what a reviewer needs.

    - create: `data`, the new object's non-empty fields;
    - update: `changes`, `{field: {"before", "after"}}` for the fields the
      branch altered only;
    - delete: nothing more than the object's identity;
    - any action: `conflicts`, `{field: {"original", "branch", "main"}}`
      when main changed the same fields since the branch did — the human
      merging will have to acknowledge them.
    """
    action = change["action"]["value"]
    original = _clean(change.get("original_data"))
    modified = _clean(change.get("modified_data"))
    summary: dict[str, Any] = {
        "id": change["id"],
        "action": action,
        "object_type": change["object_type"],
        "object_id": change["object_id"],
        "object": change.get("object_repr") or change.get("display"),
    }
    if action == "create":
        summary["data"] = {
            k: v for k, v in modified.items() if v not in (None, "", [], {})
        }
    elif action == "update":
        summary["changes"] = {
            k: {"before": original.get(k), "after": v}
            for k, v in modified.items()
            if original.get(k) != v
        }
    conflicts = change.get("conflicts")
    if conflicts:
        current = change.get("current_data") or {}
        summary["conflicts"] = {
            k: {
                "original": original.get(k),
                "branch": modified.get(k),
                "main": current.get(k),
            }
            for k in conflicts
        }
    return summary


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
