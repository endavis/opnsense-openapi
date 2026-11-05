"""Structural tests for the generate-matrix workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "generate-matrix.yml"


def _load() -> dict[Any, Any]:
    # PyYAML parses the ``on`` key as the boolean True.
    data: dict[Any, Any] = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return data


def test_matrix_comes_from_versions_job() -> None:
    job = _load()["jobs"]["generate-matrix"]
    assert job["needs"] == "versions"
    matrix = job["strategy"]["matrix"]["opnsense-version"]
    assert matrix == "${{ fromJSON(needs.versions.outputs.versions) }}"


def test_versions_job_exposes_output() -> None:
    job = _load()["jobs"]["versions"]
    assert job["outputs"]["versions"] == "${{ steps.select.outputs.versions }}"
    assert "select" in [s.get("id") for s in job["steps"]]


def test_select_step_does_not_mask_failures() -> None:
    steps = _load()["jobs"]["versions"]["steps"]
    run = next(s["run"] for s in steps if s.get("id") == "select")
    assert 'echo "versions=$(' not in run
    assert "versions=$(uv run python tools/generate_matrix_versions.py)" in run


def test_pull_request_paths_include_selection_logic() -> None:
    paths = _load()[True]["pull_request"]["paths"]
    assert "src/opnsense_openapi/specs.py" in paths
    assert "tools/generate_matrix_versions.py" in paths
