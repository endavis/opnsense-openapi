"""Tests for :func:`opnsense_openapi.client.base._auto_generate_client`.

These cover the module-level client auto-generation helper in isolation. Tests
for ``OPNsenseClient`` itself are intentionally scoped to PR-b.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from opnsense_openapi.client.base import _auto_generate_client


def test_auto_generate_returns_false_when_spec_missing(tmp_path: Path) -> None:
    """_auto_generate_client returns False if no spec file matches the version."""
    with patch(
        "opnsense_openapi.client.base.find_best_matching_spec",
        side_effect=FileNotFoundError("no spec"),
    ):
        assert _auto_generate_client("99.99") is False


def test_auto_generate_returns_true_when_client_exists(tmp_path: Path) -> None:
    """_auto_generate_client short-circuits when the generated client directory exists."""
    spec_path = tmp_path / "opnsense-24.7.json"
    spec_path.write_text("{}")

    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        assert _auto_generate_client("24.7") is True


def test_auto_generate_returns_false_when_cli_missing(tmp_path: Path) -> None:
    """_auto_generate_client returns False when openapi-python-client is absent."""
    spec_path = tmp_path / "opnsense-24.7.json"
    spec_path.write_text("{}")

    # client_dir.exists() -> False triggers the shutil.which branch.
    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        patch("pathlib.Path.exists", return_value=False),
        patch("shutil.which", return_value=None),
    ):
        assert _auto_generate_client("24.7") is False


def test_auto_generate_invokes_client_generator(tmp_path: Path) -> None:
    """_auto_generate_client shells out to openapi-python-client with expected args."""
    spec_path = tmp_path / "opnsense-24.7.json"
    spec_path.write_text("{}")

    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        patch("pathlib.Path.exists", return_value=False),
        patch("shutil.which", return_value="/usr/bin/openapi-python-client"),
        patch("subprocess.check_call") as check_call,
    ):
        assert _auto_generate_client("24.7") is True

    check_call.assert_called_once()
    cmd = check_call.call_args.args[0]
    assert cmd[0] == "openapi-python-client"
    assert "--path" in cmd
    assert str(spec_path) in cmd


def test_auto_generate_returns_false_on_generator_failure(tmp_path: Path) -> None:
    """_auto_generate_client returns False when the generator subprocess fails."""
    spec_path = tmp_path / "opnsense-24.7.json"
    spec_path.write_text("{}")

    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        patch("pathlib.Path.exists", return_value=False),
        patch("shutil.which", return_value="/usr/bin/openapi-python-client"),
        patch(
            "subprocess.check_call",
            side_effect=subprocess.CalledProcessError(returncode=1, cmd=["x"]),
        ),
    ):
        assert _auto_generate_client("24.7") is False
