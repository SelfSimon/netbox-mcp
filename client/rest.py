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
    NetBoxNotBranchableError,
    NetBoxNotFoundError,
    NetBoxNotWritableError,
    NetBoxPermissionError,
    NetBoxValidationError,
)
from .registry import ModelSpec, get_model_spec

BRANCH_HEADER = "X-NetBox-Branch"

# Every list request is bounded (NETBOX-113): `DEFAULT_LIST_LIMIT` when the
# caller gives no `limit`, and never more than `MAX_LIST_LIMIT` per request.
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 1000
# Largest batch create_many()/patch_many() send in one request (NETBOX-146):
# NetBox applies a batch in one transaction, so keep it reviewable.
MAX_BATCH_SIZE = 250


def _bounded_params(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Copy `filters` with a `limit` that is always set and capped.

    A missing `limit` becomes `DEFAULT_LIST_LIMIT`. `0` (NetBox's own "no
    limit" convention) and anything above `MAX_LIST_LIMIT` become
    `MAX_LIST_LIMIT`, so no request can ask NetBox for a whole table.
    """
    params = dict(filters or {})
    limit = params.get("limit")
    if limit is None:
        limit = DEFAULT_LIST_LIMIT
    elif not 1 <= int(limit) <= MAX_LIST_LIMIT:
        limit = MAX_LIST_LIMIT
    params["limit"] = int(limit)
    return params


def not_writable_message(resource: str, spec: ModelSpec, ui_url: str = "") -> str:
    """Why `resource` cannot be written, and where to do it by hand: not
    versioned by netbox_branching, or a `read_only` reason.

    `ui_url` is NETBOX_UI_URL: with it the message holds a full link,
    without it only the page's path — NETBOX_URL may be an internal address
    the user's browser cannot open, so it is never used here.
    """
    where = f": {ui_url}/{spec.rest_path}" if ui_url else f", page /{spec.rest_path}"
    why = (
        spec.read_only
        if spec.branchable
        else "netbox_branching does not version it, so the write would land "
        "directly on main with no review"
    )
    return (
        f"{spec.label!r} ({resource}) cannot be written through this MCP: "
        f"{why}. Ask the user to create or change it manually in the NetBox "
        f"UI{where}"
    )


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {}


def _field_errors(errors: dict[str, Any]) -> str:
    """`{"type": ["x is not a valid choice."]}` as `type: x is not a valid
    choice.`, one field after the other."""
    parts = []
    for field, messages in errors.items():
        if isinstance(messages, list):
            messages = " ".join(str(m) for m in messages)
        parts.append(f"{field}: {messages}")
    return "; ".join(parts)


def _batch_errors(errors: list[Any]) -> str:
    """NetBox's per-element errors of a batch (a list, `{}` for each
    element it accepted) as `element 2: type: ...`."""
    return "; ".join(
        f"element {index}: {_field_errors(e) if isinstance(e, dict) else e}"
        for index, e in enumerate(errors)
        if e
    )


def _guess_patch_culprits(errors: dict[str, Any], items: list[dict]) -> list[int]:
    """The elements of a batch PATCH that may have caused `errors`.

    NetBox answers a rejected batch PATCH with the errors of one element
    and no index (it validates in its own order, not the request's): the
    culprits are the elements that set a field in error, narrowed to
    those whose value the message quotes when that leaves any.
    """
    fields = [f for f in errors if f not in ("__all__", "non_field_errors")]
    candidates = [i for i, item in enumerate(items) if any(f in item for f in fields)]
    text = " ".join(str(m) for m in errors.values())
    quoted = [
        i
        for i in candidates
        if any(str(items[i][f]) in text for f in fields if f in items[i])
    ]
    return quoted or candidates


def _detail(response: httpx.Response, limit: int = 300) -> str:
    """NetBox's own explanation of an error, as ": <text>", or "".

    DRF puts it in `detail`; a proxy or a crash may answer plain text or
    HTML, kept short.
    """
    payload = _safe_json(response)
    text = payload.get("detail") if isinstance(payload, dict) else None
    if not text and not payload:
        text = response.text.strip()
    if not text:
        return ""
    text = " ".join(str(text).split())
    return f": {text[:limit]}{'...' if len(text) > limit else ''}"


def _check_batch(items: list[dict[str, Any]]) -> None:
    if not items:
        raise NetBoxValidationError("a batch needs at least one element")
    if len(items) > MAX_BATCH_SIZE:
        raise NetBoxValidationError(
            f"a batch holds at most {MAX_BATCH_SIZE} elements, got {len(items)}: "
            "split it into several calls"
        )
    bad = [i for i, item in enumerate(items) if not isinstance(item, dict)]
    if bad:
        raise NetBoxValidationError(f"element {bad[0]} of the batch is not an object")


def _simplify_reference(field: dict[str, Any]) -> dict[str, Any]:
    children = field.get("children", {})
    reference_by = [key for key in ("id", "slug", "name") if key in children]
    return {
        "type": "reference",
        "required": field.get("required", False),
        "label": field.get("label", ""),
        "reference_by": reference_by,
    }


def _is_inline_object(field: dict[str, Any]) -> bool:
    """A nested object with no id/slug/name is a value written inline
    (e.g. a front port's `rear_ports` mappings), not a reference to
    another NetBox object."""
    children = field.get("children", {})
    return not any(key in children for key in ("id", "slug", "name"))


def _simplify_children(field: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, child in field.get("children", {}).items():
        simplified = _simplify_field(child)
        if simplified is not None:
            result[name] = simplified
    return result


def _simplify_field(field: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce one raw DRF OPTIONS field to what write_resource() needs.

    Returns None when the field should be dropped entirely (read-only).
    """
    if field.get("read_only"):
        return None

    if field.get("type") == "nested object":
        if _is_inline_object(field):
            return {
                "type": "object",
                "required": field.get("required", False),
                "label": field.get("label", ""),
                "fields": _simplify_children(field),
            }
        return _simplify_reference(field)

    child = field.get("child")
    if isinstance(child, dict) and child.get("type") == "nested object":
        if _is_inline_object(child):
            return {
                "type": "list[object]",
                "required": field.get("required", False),
                "label": field.get("label", ""),
                "fields": _simplify_children(child),
            }
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


def _custom_field(definition: dict[str, Any]) -> dict[str, Any]:
    """Reduce one extras/custom-fields/ definition like _simplify_field()."""
    kind = definition.get("type")
    field: dict[str, Any] = {
        "type": kind.get("value") if isinstance(kind, dict) else kind,
        "required": bool(definition.get("required")),
    }
    for key in ("label", "description"):
        if definition.get(key):
            field[key] = definition[key]
    if definition.get("default") is not None:
        field["default"] = definition["default"]
    if definition.get("related_object_type"):
        field["related_object_type"] = definition["related_object_type"]
    choice_set = definition.get("choice_set")
    if isinstance(choice_set, dict):
        field["choice_set"] = {
            "id": choice_set.get("id"),
            "name": choice_set.get("name"),
        }
    return field


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

    def list_page(
        self, resource: str, filters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return one bounded page of objects matching `filters`.

        Always a single request. The result carries NetBox's total `count`
        next to the page (`results`) and the `limit`/`offset` actually
        applied, so a caller can tell whether it has seen everything.
        """
        return self._page(get_model_spec(resource).rest_path, filters)

    def list(
        self,
        resource: str,
        filters: dict[str, Any] | None = None,
        *,
        paginate: bool = False,
    ) -> list[dict[str, Any]]:
        """Return objects matching `filters`, one bounded page by default.

        A single request is made, limited to `filters["limit"]` or
        `DEFAULT_LIST_LIMIT`: a call with no `limit` used to follow every
        `next` link and bring back the whole table (NETBOX-113). Pass
        `paginate=True` to follow `next` on purpose — never from an MCP
        tool, whose result must stay bounded.
        """
        spec = get_model_spec(resource)
        response = self._request("GET", spec.rest_path, params=_bounded_params(filters))
        payload = response.json()
        results: list[dict[str, Any]] = list(payload["results"])

        next_url = payload.get("next") if paginate else None
        while next_url:
            response = self._request("GET", next_url)
            payload = response.json()
            results.extend(payload["results"])
            next_url = payload.get("next")

        return results

    def get(
        self,
        resource: str,
        object_id: int,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = get_model_spec(resource)
        response = self._request(
            "GET", f"{spec.rest_path}{object_id}/", params=params or None
        )
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
        if "custom_fields" in result:
            result["custom_fields"] = self._custom_fields_schema(
                spec, result["custom_fields"]
            )
        return result

    def _custom_fields_schema(
        self, spec: ModelSpec, generic: dict[str, Any]
    ) -> dict[str, Any]:
        """The custom fields defined for `spec`'s object type (NETBOX-141).

        OPTIONS only says `custom_fields` is a field; the definitions live
        in extras/custom-fields/, filtered by object type (`dcim.device`),
        which core/object-types/ maps from the resource's REST path.
        """
        app_label = spec.rest_path.split("/", 1)[0]
        endpoint = f"/api/{spec.rest_path}"
        try:
            object_types = self._page(
                "core/object-types/",
                {"app_label": app_label, "limit": MAX_LIST_LIMIT},
            )["results"]
            object_type = next(
                (
                    f"{o['app_label']}.{o['model']}"
                    for o in object_types
                    if o.get("rest_api_endpoint") == endpoint
                ),
                None,
            )
            if object_type is None:
                return generic
            definitions = self._page(
                "extras/custom-fields/",
                {"object_type": object_type, "limit": MAX_LIST_LIMIT},
            )["results"]
        except NetBoxPermissionError:
            # The schema stays useful without them: say why they're missing.
            return {
                **generic,
                "help_text": (
                    "Your NetBox token cannot read the custom field "
                    "definitions; ask the user which custom fields exist."
                ),
            }
        return {
            "type": "object",
            "required": any(cf.get("required") for cf in definitions),
            "label": generic.get("label", "Custom fields"),
            "help_text": (
                "Values by custom field name. A patch changes only the custom "
                "fields it names; null clears one."
            ),
            "fields": {cf["name"]: _custom_field(cf) for cf in definitions},
        }

    # -- Write ---------------------------------------------------------

    def create(self, resource: str, data: dict[str, Any]) -> dict[str, Any]:
        spec = self._writable_spec(resource)
        response = self._request("POST", spec.rest_path, json=data)
        return response.json()

    def create_many(
        self, resource: str, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Create every object of `items` in ONE request (NETBOX-146).

        NetBox applies the batch in one transaction: if any element is
        rejected, nothing is created, and the error names each rejected
        element by its index in `items`.
        """
        spec = self._writable_spec(resource)
        _check_batch(items)
        response = self._request("POST", spec.rest_path, json=items)
        return response.json()

    def patch_many(
        self, resource: str, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Partially update several objects in ONE request (NETBOX-146);
        each element of `items` holds the `id` of its object and the
        fields to change.

        All or nothing, like create_many(). The ids are checked first:
        NetBox would silently skip an unknown one and apply the others.
        """
        spec = self._writable_spec(resource)
        _check_batch(items)
        ids = [item.get("id") for item in items]
        bad = [
            i
            for i, v in enumerate(ids)
            if not isinstance(v, int) or isinstance(v, bool)
        ]
        if bad:
            raise NetBoxValidationError(
                f"patch_many({resource!r}): element {bad[0]} has no integer `id`; "
                "each element must hold the id of the object it changes"
            )
        if len(set(ids)) != len(ids):
            dup = sorted({v for v in ids if ids.count(v) > 1})
            raise NetBoxValidationError(
                f"patch_many({resource!r}): ids {dup} appear more than once; "
                "merge their changes into one element each"
            )
        found = self._request(
            "GET",
            spec.rest_path,
            params={"id": ids, "fields": "id", "limit": len(ids)},
        ).json()["results"]
        missing = sorted(set(ids) - {o["id"] for o in found})
        if missing:
            raise NetBoxNotFoundError(
                f"PATCH {spec.rest_path}: no {resource} with id {missing}; "
                "nothing was changed"
            )
        try:
            response = self._request("PATCH", spec.rest_path, json=items)
        except NetBoxValidationError as exc:
            if not isinstance(exc.errors, dict) or not exc.errors:
                raise
            culprits = _guess_patch_culprits(exc.errors, items)
            which = (
                f"element {culprits[0]} (id {ids[culprits[0]]})"
                if len(culprits) == 1
                else f"one of the elements {culprits}"
                if culprits
                else "an element NetBox does not name"
            )
            raise NetBoxValidationError(
                f"PATCH {spec.rest_path}: batch rejected by NetBox (400), "
                f"nothing was changed: {which}: {_field_errors(exc.errors)}",
                errors=exc.errors,
            ) from None
        return response.json()

    def update(
        self, resource: str, object_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Full replacement (PUT) of the `object_id` object."""
        spec = self._writable_spec(resource)
        response = self._request("PUT", f"{spec.rest_path}{object_id}/", json=data)
        return response.json()

    def patch(
        self, resource: str, object_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Partial update (PATCH) of the `object_id` object."""
        spec = self._writable_spec(resource)
        response = self._request("PATCH", f"{spec.rest_path}{object_id}/", json=data)
        return response.json()

    def delete(self, resource: str, object_id: int) -> None:
        """Delete the `object_id` object.

        Requires an active branch (`self.branch is not None`): a delete
        outside a branch would apply directly to `main` with no human
        review gate, which this client never allows. Raises
        NetBoxNoBranchError before any request is sent if no branch is set.
        """
        spec = self._writable_spec(resource)
        if not self._branch:
            raise NetBoxNoBranchError(
                "delete() requires an active netbox_branching branch; "
                "direct writes to main are not allowed"
            )
        self._request("DELETE", f"{spec.rest_path}{object_id}/")

    # -- Internals -------------------------------------------------------

    def _writable_spec(self, resource: str) -> ModelSpec:
        """The resource's spec, or NetBoxNotBranchableError when
        netbox_branching would send the write straight to main, or
        NetBoxNotWritableError when the MCP only reads it (`read_only`)."""
        spec = get_model_spec(resource)
        if not spec.writable:
            error = (
                NetBoxNotWritableError if spec.branchable else NetBoxNotBranchableError
            )
            raise error(
                not_writable_message(resource, spec, self._settings.netbox_ui_url)
            )
        return spec

    def _page(self, path: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        params = _bounded_params(filters)
        payload = self._request("GET", path, params=params).json()
        return {
            "count": payload["count"],
            "limit": params["limit"],
            "offset": int(params.get("offset") or 0),
            "results": payload["results"],
        }

    def _raise_branch_refusal(self, method: str, path: str, text: str) -> None:
        """Turn netbox_branching's plain-text refusals of `X-NetBox-Branch`
        into errors that say what to do (NETBOX-145). Returns for any other
        text."""
        if text == "Invalid branch identifier":
            raise NetBoxNotFoundError(
                f"{method} {path}: no branch with schema_id {self._branch!r}. "
                "Pass the `schema_id` of a branch from list_branches(), not "
                "its name or id."
            )
        if "is not ready for use" in text:
            raise NetBoxValidationError(
                f"{method} {path}: {text}. Wait until list_branches() shows "
                "it ready, then try again."
            )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise NetBoxConnectionError(f"NetBox timeout on {method} {path}") from exc
        except httpx.HTTPError as exc:
            raise NetBoxConnectionError(
                f"Failed to connect to NetBox on {method} {path}: {exc}"
            ) from exc

        code = response.status_code
        if code in (401, 403):
            raise NetBoxPermissionError(
                f"{method} {path}: permission denied by NetBox ({code})"
                f"{_detail(response)}"
            )
        if code == 404:
            raise NetBoxNotFoundError(
                f"{method} {path}: object not found (404){_detail(response)}"
            )
        if code == 400:
            errors = _safe_json(response)
            if not errors and self._branch:
                self._raise_branch_refusal(method, path, response.text.strip())
            if isinstance(errors, list):
                raise NetBoxValidationError(
                    f"{method} {path}: batch rejected by NetBox (400), nothing "
                    f"was written: {_batch_errors(errors) or errors}",
                    errors=errors,
                )
            raise NetBoxValidationError(
                f"{method} {path}: data rejected by NetBox (400): "
                f"{errors or _detail(response)[2:]}",
                errors=errors,
            )
        if code == 429:
            raise NetBoxConnectionError(
                f"{method} {path}: NetBox rate limit reached (429)"
            )
        if code >= 500:
            raise NetBoxConnectionError(
                f"{method} {path}: NetBox server error ({code}){_detail(response)}"
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise NetBoxConnectionError(
                f"{method} {path}: unexpected HTTP error ({code}){_detail(response)}"
            ) from exc

        return response
