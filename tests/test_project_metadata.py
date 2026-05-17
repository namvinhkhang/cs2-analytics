"""Project metadata tests for reproducible local setup commands."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_default_uv_dev_group_includes_documented_validation_tools() -> None:
    """Fresh clones should have the executables used by README validation commands."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = pyproject["dependency-groups"]["dev"]
    package_names = {
        dependency.split("[", 1)[0].split(">=", 1)[0] for dependency in dev_dependencies
    }

    assert {"pytest", "ruff"}.issubset(package_names)
