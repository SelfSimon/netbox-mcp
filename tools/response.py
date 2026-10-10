"""Shared shaping of tool results: list envelopes and the size cap.

Every MCP tool result goes through one of the three helpers below, so the
rules hold for dedicated and generic tools alike:

- a list is returned as an envelope carrying NetBox's total `count` and a
  `truncated` flag, so the caller always knows whether it saw everything
  (NETBOX-113);
- no result may exceed `max_response_bytes()` once serialized (NETBOX-116).
  MCP clients cap a tool result at roughly 1 MB and fail opaquely beyond
  it; bounding the number of items is not enough, since a single NetBox
  object can be large (`config_context`, `custom_fields`, nested objects).

The default cap is well under 1 MB on purpose: FastMCP sends a dict result
twice (as text content and as structured content), so the bytes on the wire
are about double what is measured here.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_MAX_RESPONSE_BYTES = 400_000

# Room kept for the envelope's own keys around `results`.
_ENVELOPE_RESERVE = 512

_REFINE_HINT = (
    "narrow the filters, lower `limit`, or pass `brief=True` / `fields=[...]` "
    "to get smaller objects"
)


class ResponseTooLargeError(ValueError):
    """A single object is larger than the response size cap."""


def max_response_bytes() -> int:
    """Size cap for one tool result, from `MCP_MAX_RESPONSE_BYTES`."""
    return int(os.environ.get("MCP_MAX_RESPONSE_BYTES", DEFAULT_MAX_RESPONSE_BYTES))


def _size(value: Any) -> int:
    return len(
        json.dumps(
            value, separators=(",", ":"), ensure_ascii=False, default=str
        ).encode("utf-8")
    )


def selection_params(
    brief: bool = False, fields: list[str] | None = None
) -> dict[str, Any]:
    """NetBox query params for field selection (NETBOX-114)."""
    params: dict[str, Any] = {}
    if brief:
        params["brief"] = True
    if fields:
        params["fields"] = ",".join(fields)
    return params


def list_response(page: dict[str, Any]) -> dict[str, Any]:
    """Build the list envelope from a page (`count`, `offset`, `results`).

    Items are kept in order until the size cap is reached; the rest of the
    page is dropped and `truncated`/`next_offset` tell the caller where to
    resume. `truncated` is also true when NetBox simply has more objects
    than this page holds.
    """
    budget = max_response_bytes() - _ENVELOPE_RESERVE
    results: list[Any] = []
    used = 0
    for item in page["results"]:
        used += _size(item) + 1
        if used > budget:
            break
        results.append(item)

    offset = page["offset"]
    count = page["count"]
    returned = len(results)
    truncated = offset + returned < count
    response: dict[str, Any] = {
        "count": count,
        "returned": returned,
        "offset": offset,
        "truncated": truncated,
        "next_offset": offset + returned if truncated else None,
        "results": results,
    }
    if returned < len(page["results"]):
        if returned:
            response["hint"] = (
                f"Stopped after {returned} objects to stay under the response "
                f"size cap: continue from `next_offset`, or {_REFINE_HINT}."
            )
        else:
            response["hint"] = (
                "The next object alone exceeds the response size cap: pass "
                "`brief=True` or `fields=[...]` to get a smaller object."
            )
    return response


def object_response(
    value: Any, hint: str = "pass `fields=[...]` or `brief=True`"
) -> Any:
    """Return a single object as-is, or raise if it exceeds the size cap."""
    size = _size(value)
    limit = max_response_bytes()
    if size > limit:
        raise ResponseTooLargeError(
            f"Response is {size} bytes, over the {limit}-byte cap — {hint}."
        )
    return value


def write_response(value: Any) -> Any:
    """Return a write's result, reduced to a reference if it is too large.

    The write has already succeeded at this point, so an oversized object
    must not surface as an error: only its identifying keys are returned.
    """
    if not isinstance(value, dict) or _size(value) <= max_response_bytes():
        return value
    reduced = {key: value[key] for key in ("id", "url", "display") if key in value}
    reduced["truncated"] = True
    reduced["hint"] = (
        "The write succeeded; the object is too large to return in full. "
        "Read it back with `fields=[...]` if you need more."
    )
    return reduced
