"""Tests for :func:`opnsense_openapi.client.base._auto_generate_client`.

These cover the module-level client auto-generation helper in isolation. Tests
for ``OPNsenseClient`` itself are intentionally scoped to PR-b.

The helper raises ``RuntimeError`` with a cause-tagged message for each of
three distinct failure modes (spec missing, CLI missing, codegen failed) and
returns the *resolved* spec version on success.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from opnsense_openapi.client.base import _auto_generate_client, _resolved_module_dir


def test_auto_generate_raises_when_spec_missing() -> None:
    """_auto_generate_client raises a spec-missing error when no spec resolves."""
    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            side_effect=FileNotFoundError("no spec"),
        ),
        pytest.raises(RuntimeError) as exc_info,
    ):
        _auto_generate_client("99.99")

    msg = str(exc_info.value)
    assert "No OpenAPI spec for version 99.99" in msg
    assert "available=" in msg
    assert "opnsense-openapi generate 99.99" in msg


def test_auto_generate_returns_resolved_version_when_client_exists(tmp_path: Path) -> None:
    """_auto_generate_client short-circuits when the generated client directory exists.

    The return value is the *resolved* spec version (the version segment of
    the spec filename), not the raw input.
    """
    spec_path = tmp_path / "opnsense-24.7.json"
    spec_path.write_text("{}")

    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        assert _auto_generate_client("24.7") == "24.7"


def test_auto_generate_raises_when_cli_missing(tmp_path: Path) -> None:
    """_auto_generate_client raises a CLI-missing error when openapi-python-client is absent."""
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
        pytest.raises(RuntimeError) as exc_info,
    ):
        _auto_generate_client("24.7")

    msg = str(exc_info.value)
    assert "openapi-python-client is not on PATH" in msg
    assert "uv tool install openapi-python-client" in msg
    assert str(spec_path) in msg


def test_auto_generate_invokes_client_generator(tmp_path: Path) -> None:
    """_auto_generate_client shells out to openapi-python-client with expected args.

    On success, returns the resolved spec version.
    """
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
        assert _auto_generate_client("24.7") == "24.7"

    check_call.assert_called_once()
    cmd = check_call.call_args.args[0]
    assert cmd[0] == "openapi-python-client"
    assert "--path" in cmd
    assert str(spec_path) in cmd


def test_auto_generate_raises_with_stderr_on_generator_failure(tmp_path: Path) -> None:
    """_auto_generate_client raises a codegen-failed error containing the captured stderr."""
    spec_path = tmp_path / "opnsense-24.7.json"
    spec_path.write_text("{}")

    captured_stderr = b"openapi-python-client: error: bad ref #/components/schemas/Foo"

    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        patch("pathlib.Path.exists", return_value=False),
        patch("shutil.which", return_value="/usr/bin/openapi-python-client"),
        patch(
            "subprocess.check_call",
            side_effect=subprocess.CalledProcessError(
                returncode=2, cmd=["x"], stderr=captured_stderr
            ),
        ),
        pytest.raises(RuntimeError) as exc_info,
    ):
        _auto_generate_client("24.7")

    msg = str(exc_info.value)
    assert "openapi-python-client failed for version 24.7" in msg
    assert str(spec_path) in msg
    assert "returncode=2" in msg
    assert "bad ref #/components/schemas/Foo" in msg


# --- Module-path stability across security-patch revisions ----------------


def test_resolved_module_dir_strips_security_patch_suffix(tmp_path: Path) -> None:
    """``26.1.6`` and ``26.1.6_2`` resolve to the same generated-client directory.

    This is the core invariant for issue #34: distinct security-patch revisions
    of the same release must share a single generated client, since the
    OpenAPI surface does not change between them.
    """
    spec_path = tmp_path / "opnsense-26.1.6.json"
    spec_path.write_text("{}")

    with patch(
        "opnsense_openapi.client.base.find_best_matching_spec",
        return_value=spec_path,
    ):
        _, resolved_a, dir_a = _resolved_module_dir("26.1.6")
        _, resolved_b, dir_b = _resolved_module_dir("26.1.6_2")

    assert resolved_a == resolved_b == "26.1.6"
    assert dir_a == dir_b
    assert dir_a.name == "v26_1_6"


def test_auto_generate_skips_codegen_for_security_patch_revision(tmp_path: Path) -> None:
    """A second invocation with a ``_N`` suffix finds the existing client.

    Sequence:
        1. First call (raw version ``26.1.6``) — no client yet, codegen runs.
        2. Second call (raw version ``26.1.6_2``, same resolver target) —
           the canonical ``v26_1_6`` directory now exists, so codegen is
           **not** invoked again.

    Both calls must return the resolved version (``"26.1.6"``).
    """
    spec_path = tmp_path / "opnsense-26.1.6.json"
    spec_path.write_text("{}")

    # Track which client_dir paths the auto-generator considered "existing".
    existed: set[str] = set()

    def fake_exists(self: Path) -> bool:
        return str(self) in existed

    def fake_check_call(cmd: list[str], **_: object) -> int:
        # Record that this run "created" the client_dir, so the next
        # client_dir.exists() returns True.
        idx = cmd.index("--output-path")
        existed.add(cmd[idx + 1])
        return 0

    with (
        patch(
            "opnsense_openapi.client.base.find_best_matching_spec",
            return_value=spec_path,
        ),
        patch("pathlib.Path.exists", new=fake_exists),
        patch("shutil.which", return_value="/usr/bin/openapi-python-client"),
        patch("subprocess.check_call", side_effect=fake_check_call) as check_call,
    ):
        # First call: no v26_1_6 dir yet → codegen runs.
        assert _auto_generate_client("26.1.6") == "26.1.6"
        # Second call with security-patch suffix: short-circuits.
        assert _auto_generate_client("26.1.6_2") == "26.1.6"

    # codegen invoked exactly once across both calls.
    assert check_call.call_count == 1
