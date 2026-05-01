"""Tests for :func:`opnsense_openapi.client.base._auto_generate_client`.

These cover the module-level client auto-generation helper in isolation. Tests
for ``OPNsenseClient`` itself are intentionally scoped to PR-b.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from opnsense_openapi.client.base import _auto_generate_client, _resolved_module_dir


def test_auto_generate_returns_false_when_spec_missing() -> None:
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
        assert _auto_generate_client("26.1.6") is True
        # Second call with security-patch suffix: short-circuits.
        assert _auto_generate_client("26.1.6_2") is True

    # codegen invoked exactly once across both calls.
    assert check_call.call_count == 1
