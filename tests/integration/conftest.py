"""Common guard for integration tests: they require a real NetBox instance.

This fixture makes them skip (rather than fail) as long as NETBOX_URL/
NETBOX_API_TOKEN aren't set, which allows committing these tests without
breaking an unconfigured local `pytest -m integration` run.
"""

import os

import pytest


def _missing_env_vars() -> list[str]:
    required = ("NETBOX_URL", "NETBOX_API_TOKEN")
    return [name for name in required if not os.environ.get(name)]


@pytest.fixture(autouse=True)
def _require_real_netbox_instance():
    missing = _missing_env_vars()
    if missing:
        pytest.skip(
            "Integration tests disabled: missing variable(s) "
            f"{', '.join(missing)} (requires a real NetBox instance "
            "with netbox_branching installed)."
        )
