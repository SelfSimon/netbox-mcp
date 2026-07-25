"""NetBox client, 100% REST API — read and write.

Going through the REST API (rather than the Django ORM) gives read and
write the exact same behavior for free: NetBox's native FilterSets,
serializers, object-level permissions, changelog and webhooks all apply
identically, with no logic duplicated here.

Branch-first writes: `netbox_branching` scopes a request to a branch via
the `X-NetBox-Branch` header (constant `BRANCH_HEADER` below). A client
instance is bound to at most one branch (or none, meaning `main`) for its
whole lifetime — every list/get/count/create/update/patch/delete call goes
through the same scope. `delete()` refuses to run without an active branch:
nothing destructive ever reaches `main` directly, since merging a branch
into `main` is a human-only action outside this client's capabilities (see
`branches.py`).
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from .config import ClientSettings, get_settings
from .exceptions import (
    NetBoxConnectionError,
    NetBoxNoBranchError,
    NetBoxNotFoundError,
    NetBoxPermissionError,
    NetBoxValidationError,
)
from .registry import get_model_spec

BRANCH_HEADER = "X-NetBox-Branch"


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {}


def _simplify_reference(field: dict[str, Any]) -> dict[str, Any]:
    children = field.get("children", {})
    reference_by = [key for key in ("id", "slug", "name") if key in children]
    return {
        "type": "reference",
        "required": field.get("required", False),
        "label": field.get("label", ""),
        "reference_by": reference_by,
    }


def _simplify_field(field: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce one raw DRF OPTIONS field to what write_resource() needs.

    Returns None when the field should be dropped entirely (read-only).
    """
    if field.get("read_only"):
        return None

    if field.get("type") == "nested object":
        return _simplify_reference(field)

    child = field.get("child")
    if isinstance(child, dict) and child.get("type") == "nested object":
        reference = _simplify_reference(child)
        return {
            "type": "list[reference]",
            "required": field.get("required", False),
            "label": field.get("label", ""),
            "reference_by": reference["reference_by"],
        }

    simplified: dict[str, Any] = {
        "type": field.get("type"),
        "required": field.get("required", False),
    }
    if "label" in field:
        simplified["label"] = field["label"]
    if "choices" in field:
        simplified["choices"] = field["choices"]
    if "max_length" in field:
        simplified["max_length"] = field["max_length"]
    if "help_text" in field:
        simplified["help_text"] = field["help_text"]
    return simplified


class NetBoxRestClient:
    """HTTP client for the local NetBox REST API."""

    def __init__(
        self,
        settings: ClientSettings | None = None,
        branch: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._branch = branch

        headers = {
            "Authorization": f"Token {self._settings.netbox_api_token}",
            "Accept": "application/json",
        }
        if branch:
            headers[BRANCH_HEADER] = branch

        self._client = httpx.Client(
            base_url=f"{self._settings.netbox_url}/api/",
            headers=headers,
            timeout=self._settings.timeout,
        )

    @property
    def branch(self) -> str | None:
        return self._branch

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- Read --------------------------------------------------------

    def list(
        self, resource: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Return objects matching `filters`.

        Auto-paginates through every page when `filters` has no explicit
        `limit`. If it does, a single request is made and that page is
        returned as-is: previously `next` was always followed regardless
        of `limit`, so a caller-supplied limit was silently ignored and
        the full result set came back anyway (NETBOX-96).
        """
        spec = get_model_spec(resource)
        results: list[dict[str, Any]] = []

        response = self._request("GET", spec.rest_path, params=filters)
        payload = response.json()
        results.extend(payload["results"])

        if filters and filters.get("limit") is not None:
            return results

        next_url = payload.get("next")
        while next_url:
            response = self._request("GET", next_url)
            payload = response.json()
            results.extend(payload["results"])
            next_url = payload.get("next")

        return results

    def get(self, resource: str, object_id: int) -> dict[str, Any]:
        spec = get_model_spec(resource)
        response = self._request("GET", f"{spec.rest_path}{object_id}/")
        return response.json()

    def count(self, resource: str, filters: dict[str, Any] | None = None) -> int:
        spec = get_model_spec(resource)
        params = {**(filters or {}), "limit": 1}
        response = self._request("GET", spec.rest_path, params=params)
        return response.json()["count"]

    def schema(self, resource: str) -> dict[str, Any]:
        """Simplified write schema for `resource` (for write_resource()).

        Issues OPTIONS against the resource's REST path and reduces DRF's
        raw field metadata to what an agent needs before writing: required/
        optional, type, label, enum choices, and related objects reduced to
        how to reference them (id/slug/name), not their own writable
        fields (NETBOX-99/100/101).
        """
        spec = get_model_spec(resource)
        response = self._request("OPTIONS", spec.rest_path)
        raw_fields = response.json().get("actions", {}).get("POST", {})
        result: dict[str, Any] = {}
        for name, field in raw_fields.items():
            simplified = _simplify_field(field)
            if simplified is not None:
                result[name] = simplified
        return result

    # -- Write ---------------------------------------------------------

    def create(self, resource: str, data: dict[str, Any]) -> dict[str, Any]:
        spec = get_model_spec(resource)
        response = self._request("POST", spec.rest_path, json=data)
        return response.json()

    def update(
        self, resource: str, object_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Full replacement (PUT) of the `object_id` object."""
        spec = get_model_spec(resource)
        response = self._request("PUT", f"{spec.rest_path}{object_id}/", json=data)
        return response.json()

    def patch(
        self, resource: str, object_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Partial update (PATCH) of the `object_id` object."""
        spec = get_model_spec(resource)
        response = self._request("PATCH", f"{spec.rest_path}{object_id}/", json=data)
        return response.json()

    def delete(self, resource: str, object_id: int) -> None:
        """Delete the `object_id` object.

        Requires an active branch (`self.branch is not None`): a delete
        outside a branch would apply directly to `main` with no human
        review gate, which this client never allows. Raises
        NetBoxNoBranchError before any request is sent if no branch is set.
        """
        if not self._branch:
            raise NetBoxNoBranchError(
                "delete() requires an active netbox_branching branch; "
                "direct writes to main are not allowed"
            )
        spec = get_model_spec(resource)
        self._request("DELETE", f"{spec.rest_path}{object_id}/")

    # -- Internals -------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise NetBoxConnectionError(f"NetBox timeout on {method} {path}") from exc
        except httpx.HTTPError as exc:
            raise NetBoxConnectionError(
                f"Failed to connect to NetBox on {method} {path}: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise NetBoxPermissionError(f"{method} {path}: permission denied by NetBox")
        if response.status_code == 404:
            raise NetBoxNotFoundError(f"{method} {path}: object not found")
        if response.status_code == 400:
            errors = _safe_json(response)
            raise NetBoxValidationError(
                f"{method} {path}: data rejected by NetBox: {errors}",
                errors=errors,
            )
        if response.status_code == 429:
            raise NetBoxConnectionError(
                f"{method} {path}: NetBox rate limit reached (429)"
            )
        if response.status_code >= 500:
            raise NetBoxConnectionError(
                f"{method} {path}: NetBox server error ({response.status_code})"
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise NetBoxConnectionError(
                f"{method} {path}: unexpected HTTP error ({response.status_code})"
            ) from exc

        return response
