"""Repo tooling consistency checks."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pre_commit_ruff_hook_matches_the_pinned_ruff():
    # Dependabot bumps ruff in pyproject.toml but not the pre-commit hook
    # rev: without this check the hook and CI can lint with different ruff
    # versions. Fix by setting the hook's `rev` to the pinned version.
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pins = [
        d
        for d in pyproject["project"]["optional-dependencies"]["dev"]
        if d.startswith("ruff==")
    ]
    assert len(pins) == 1, "pyproject.toml must pin ruff exactly (ruff==X.Y.Z)"
    pinned = pins[0].removeprefix("ruff==")

    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    match = re.search(
        r"repo:\s*https://github\.com/astral-sh/ruff-pre-commit\s*\n\s*rev:\s*v?(\S+)",
        config,
    )
    assert match, "ruff-pre-commit hook not found in .pre-commit-config.yaml"

    assert match.group(1) == pinned, (
        f".pre-commit-config.yaml runs ruff {match.group(1)}, pyproject.toml "
        f"pins {pinned}: set the ruff-pre-commit `rev` to v{pinned}"
    )
