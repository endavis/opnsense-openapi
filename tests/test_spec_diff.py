"""Tests for the spec diff library function and CLI command."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import opnsense_openapi
from opnsense_openapi import SpecDiff, diff_specs
from opnsense_openapi.cli import app

runner = CliRunner()
FakeSpecs = Callable[[dict[str, dict[str, dict[str, object]]]], Path]

SPECS: dict[str, dict[str, dict[str, object]]] = {
    "30.1.1": {
        "/api/core/a/keep": {"get": {}},
        "/api/core/a/gone": {"post": {}},
        "/api/fw/b/multi": {"get": {}},
    },
    "30.1.5": {
        "/api/core/a/keep": {"get": {}},
        "/api/core/a/new": {"post": {}},
        "/api/fw/b/multi": {"get": {}, "post": {}},
    },
}


def test_added_and_removed(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = diff_specs("30.1.1", "30.1.5")
    assert isinstance(result, SpecDiff)
    assert result.added == [("/api/core/a/new", "POST"), ("/api/fw/b/multi", "POST")]
    assert result.removed == [("/api/core/a/gone", "POST")]
    assert not result.is_empty
    assert result.from_spec.name == "opnsense-30.1.1.json"


def test_identical_is_empty(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = diff_specs("30.1.5", "30.1.5")
    assert result.is_empty


def test_floor_and_suffix_resolution(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = diff_specs("30.1.3", "30.1.5_2")
    assert result.from_spec.name == "opnsense-30.1.1.json"
    assert result.to_spec.name == "opnsense-30.1.5.json"
    assert result.added


def test_module_filter(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = diff_specs("30.1.1", "30.1.5", module="CORE")
    assert result.added == [("/api/core/a/new", "POST")]
    assert result.removed == [("/api/core/a/gone", "POST")]


def test_unknown_module_raises(fake_specs: FakeSpecs) -> None:
    with (
        patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)),
        pytest.raises(ValueError, match="Unknown module"),
    ):
        diff_specs("30.1.1", "30.1.5", module="nope")


def test_unknown_version_raises(fake_specs: FakeSpecs) -> None:
    with (
        patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)),
        pytest.raises(FileNotFoundError),
    ):
        diff_specs("1.0.0", "30.1.5")


def test_exports() -> None:
    assert "diff_specs" in opnsense_openapi.__all__
    assert "SpecDiff" in opnsense_openapi.__all__


def test_cli_text_real_specs() -> None:
    result = runner.invoke(app, ["diff", "26.1.6", "26.1.11"])
    assert result.exit_code == 0
    assert "Comparing opnsense-26.1.6.json -> opnsense-26.1.11.json" in result.output


def test_cli_text_format(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = runner.invoke(app, ["diff", "30.1.1", "30.1.5"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0] == "Comparing opnsense-30.1.1.json -> opnsense-30.1.5.json"
    assert "core:" in lines
    assert "  + POST /api/core/a/new" in lines
    assert "  - POST /api/core/a/gone" in lines
    assert lines[-1] == "2 added, 1 removed"


def test_cli_json(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = runner.invoke(app, ["diff", "30.1.1", "30.1.5", "--format", "json", "-m", "core"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["from"] == {"version": "30.1.1", "spec": "opnsense-30.1.1.json"}
    assert data["to"] == {"version": "30.1.5", "spec": "opnsense-30.1.5.json"}
    assert data["module"] == "core"
    assert data["added"] == [{"method": "POST", "path": "/api/core/a/new"}]
    assert data["removed"] == [{"method": "POST", "path": "/api/core/a/gone"}]


def test_cli_module_header(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = runner.invoke(app, ["diff", "30.1.1", "30.1.5", "-m", "core"])
    assert result.output.splitlines()[0].endswith("(module: core)")
    assert "fw:" not in result.output


def test_cli_unknown_version(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = runner.invoke(app, ["diff", "1.0.0", "30.1.5"])
    assert result.exit_code == 1
    assert "Available versions: 30.1.1, 30.1.5" in result.output


def test_cli_unknown_module(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = runner.invoke(app, ["diff", "30.1.1", "30.1.5", "-m", "nope"])
    assert result.exit_code == 1
    assert "Unknown module" in result.output


def test_cli_identical(fake_specs: FakeSpecs) -> None:
    with patch("opnsense_openapi.specs.get_specs_dir", return_value=fake_specs(SPECS)):
        result = runner.invoke(app, ["diff", "30.1.5", "30.1.5"])
    assert result.exit_code == 0
    assert "No endpoint changes." in result.output
