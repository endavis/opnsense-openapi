"""Pre-Flask error-handling tests for the ``serve-docs`` CLI command.

This module covers only the *pre*-Flask code paths in
:func:`opnsense_openapi.cli.serve_docs` — argument validation, missing
``ui`` extra (Flask import failure), missing spec file, and ``--list``.
The Flask route handler functions themselves (``api_spec``, ``proxy``,
``proxy_options``, ``index``) are interactive HTTP handlers and are
marked ``# pragma: no cover``.
"""

from __future__ import annotations

import builtins
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from opnsense_openapi.cli import app

runner = CliRunner()


# === --list / --no-auto-detect arg validation (no Flask required) ===


def test_serve_docs_list_versions_exits_zero() -> None:
    """``--list`` must print available versions and return without invoking Flask."""
    fake_versions = ["24.7.0", "25.1.0"]
    with patch("opnsense_openapi.cli.list_available_specs", return_value=fake_versions):
        result = runner.invoke(app, ["serve-docs", "--list"])

    assert result.exit_code == 0
    assert "Available OPNsense API spec versions" in result.stdout
    for version in fake_versions:
        assert version in result.stdout


def test_serve_docs_no_auto_detect_without_version_errors() -> None:
    """``--no-auto-detect`` requires ``--version`` per cli.py argument-validation logic."""
    result = runner.invoke(app, ["serve-docs", "--no-auto-detect"])

    assert result.exit_code == 1
    assert "--no-auto-detect requires --version" in result.stderr


# === Missing 'ui' extra: Flask import fails ===


def test_serve_docs_missing_flask_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Flask is not installed, ``serve-docs`` exits with the install hint."""
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "flask" or name.startswith("flask"):
            raise ImportError("No module named 'flask'")
        if name == "flask_swagger_ui" or name.startswith("flask_swagger_ui"):
            raise ImportError("No module named 'flask_swagger_ui'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    # Drop any stale flask modules from sys.modules so the import-from path runs.
    for mod_name in list(sys.modules):
        if mod_name.startswith(("flask", "flask_swagger_ui")):
            monkeypatch.delitem(sys.modules, mod_name, raising=False)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = runner.invoke(app, ["serve-docs", "--no-auto-detect", "--version", "25.7.6"])

    assert result.exit_code == 1
    assert "Flask dependencies not installed" in result.stderr
    assert "uv pip install opnsense-openapi[ui]" in result.stdout


# === Spec lookup failures (post-Flask import) ===


def test_serve_docs_no_spec_for_explicit_version() -> None:
    """An explicit ``--version`` whose spec is missing prints the unavailable error."""
    # Force find_best_matching_spec to raise FileNotFoundError so the typer.Exit branch fires.
    with (
        patch("opnsense_openapi.cli.find_best_matching_spec", side_effect=FileNotFoundError),
        patch("opnsense_openapi.cli.list_available_specs", return_value=["24.7.0"]),
    ):
        result = runner.invoke(app, ["serve-docs", "--no-auto-detect", "--version", "99.9.9"])

    assert result.exit_code == 1
    assert "No spec file found for version 99.9.9" in result.stderr
    # Helpful message lists known versions
    assert "Available versions" in result.stdout


def test_serve_docs_no_specs_at_all() -> None:
    """When auto-detect fails AND no specs are on disk, ``serve-docs`` errors out.

    This exercises the ``available = list_available_specs()`` empty branch.
    """
    # Auto-detection raises so version_to_use stays None.
    with (
        patch("opnsense_openapi.cli.list_available_specs", return_value=[]),
        patch(
            "opnsense_openapi.client.OPNsenseClient",
            side_effect=Exception("no network"),
        ),
    ):
        result = runner.invoke(app, ["serve-docs"])

    assert result.exit_code == 1
    assert "No spec files found in specs directory" in result.stderr


def test_serve_docs_auto_detect_picks_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    """When auto-detect fails but specs exist, the latest spec is used.

    Tests the ``available[-1]`` branch when ``version_to_use`` is None.
    Stops execution with ``flask_app.run`` patched out so the test doesn't block.
    """
    monkeypatch.setenv("OPNSENSE_URL", "")  # Ensure proxy config does not fire
    monkeypatch.setenv("OPNSENSE_API_KEY", "")
    monkeypatch.setenv("OPNSENSE_API_SECRET", "")

    with (
        patch("opnsense_openapi.cli.list_available_specs", return_value=["24.7.0", "25.1.0"]),
        patch("opnsense_openapi.cli.find_best_matching_spec", return_value=Path("spec.json")),
        patch(
            "opnsense_openapi.client.OPNsenseClient",
            side_effect=Exception("no network"),
        ),
        # Stub Flask to avoid running an actual server.
        patch("flask.Flask") as flask_cls,
        patch("flask_swagger_ui.get_swaggerui_blueprint", return_value=MagicMock()),
    ):
        flask_app_instance = MagicMock()
        flask_cls.return_value = flask_app_instance

        result = runner.invoke(app, ["serve-docs"])

    # The command should reach Flask startup; we assert the latest version was selected.
    assert "Using latest available spec: 25.1.0" in result.stdout
    flask_app_instance.run.assert_called_once()
