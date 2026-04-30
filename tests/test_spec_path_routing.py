"""Structural lint for spec path routing.

This test suite verifies that every ``/api/{module}/{controller}/{action}``
path in a committed OpenAPI spec resolves to a real ``*Controller.php`` file
in the matching OPNsense source archive. It is the structural lint counterpart
to issue #32, which shipped 56 specs whose paths did not reverse-map to real
controllers because the generator was emitting collapsed-lowercase URL
segments instead of snake_case.

Two layers of tests live here:

* The marked lint test (``requires_opnsense_source``) loads the latest
  committed spec via :func:`opnsense_openapi.list_available_specs` and walks
  every path. It downloads the source archive on demand via
  :class:`opnsense_openapi.downloader.SourceDownloader` and skips with a
  clear reason when the download cannot proceed (e.g., no network).
* Unmarked unit tests exercise the path-checking helper against a synthetic
  fake source tree under ``tmp_path``. These run on every CI pass and
  demonstrate that the lint catches the #32 regression class plus the
  case-insensitive module fallback that mirrors OPNsense's
  ``Mvc/Router.php:78-89``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from opnsense_openapi import get_spec_path, list_available_specs
from opnsense_openapi.downloader import SourceDownloader
from opnsense_openapi.utils import to_class_name

PATH_PATTERN = re.compile(r"^/api/([^/]+)/([^/]+)/([^/]+)(?:/.*)?$")


def _resolve_module_dir(controllers_root: Path, module: str) -> Path | None:
    """Resolve a URL module segment to its on-disk directory.

    OPNsense's ``Mvc/Router.php`` (lines 78-89) falls back to a
    case-insensitive lookup when the literal module name does not match a
    namespace directory. This mirrors that behavior so e.g. ``/api/dhcrelay``
    resolves to ``OPNsense/DHCRelay`` and ``/api/openvpn`` resolves to
    ``OPNsense/OpenVPN``.

    Args:
        controllers_root: Path to the ``OPNsense/`` directory containing
            module subdirectories.
        module: The module segment from a URL path (e.g., ``"dhcrelay"``).

    Returns:
        The resolved module directory, or ``None`` if no case-insensitive
        match exists.
    """
    direct = controllers_root / module
    if direct.is_dir():
        return direct

    module_lower = module.lower()
    for entry in controllers_root.iterdir():
        if entry.is_dir() and entry.name.lower() == module_lower:
            return entry
    return None


def check_spec_paths(spec: dict[str, Any], controllers_root: Path) -> list[tuple[str, str]]:
    """Validate that every spec path resolves to a real controller file.

    For each path of the form ``/api/{module}/{controller}/{action}[/...]``,
    asserts that ``{controllers_root}/{module}/Api/{Controller}Controller.php``
    exists, where ``{Controller}`` is :func:`to_class_name` applied to the
    URL controller segment. Module resolution is case-insensitive to match
    ``Mvc/Router.php``'s namespace fallback.

    Args:
        spec: A loaded OpenAPI spec dict (must contain a ``paths`` key).
        controllers_root: Path to the ``OPNsense/`` directory inside a
            downloaded source archive.

    Returns:
        A list of ``(path, reason)`` tuples for every path that does not
        resolve. An empty list means every path resolved successfully.
    """
    failures: list[tuple[str, str]] = []
    paths: dict[str, Any] = spec.get("paths", {})

    for path in paths:
        match = PATH_PATTERN.match(path)
        if not match:
            # Defensive: skip paths that don't match the 4+-segment shape.
            # A well-formed spec shouldn't contain these, but we don't want
            # to crash the lint over a malformed entry.
            continue

        module, controller, _ = match.groups()
        module_dir = _resolve_module_dir(controllers_root, module)
        if module_dir is None:
            failures.append(
                (
                    path,
                    f"module directory not found: no case-insensitive match for "
                    f"{module!r} under {controllers_root}",
                )
            )
            continue

        expected_filename = f"{to_class_name(controller)}Controller.php"
        expected_file = module_dir / "Api" / expected_filename
        if not expected_file.is_file():
            failures.append(
                (
                    path,
                    f"controller file not found: expected {expected_file} "
                    f"(controller segment {controller!r} -> "
                    f"{to_class_name(controller)}Controller.php)",
                )
            )

    return failures


def _make_fake_controller_tree(root: Path, controllers: dict[str, list[str]]) -> Path:
    """Create a synthetic ``OPNsense/<Module>/Api/<File>Controller.php`` tree.

    Args:
        root: Directory under which the ``OPNsense/`` tree is materialized.
        controllers: Mapping of module name (e.g., ``"Interfaces"``) to a
            list of controller filenames (e.g., ``["VlanSettingsController.php"]``).

    Returns:
        Path to the created ``OPNsense/`` directory (suitable to pass as
        ``controllers_root`` to :func:`check_spec_paths`).
    """
    opnsense_root = root / "OPNsense"
    for module, files in controllers.items():
        api_dir = opnsense_root / module / "Api"
        api_dir.mkdir(parents=True, exist_ok=True)
        for filename in files:
            (api_dir / filename).write_text("<?php // synthetic test fixture\n", encoding="utf-8")
    return opnsense_root


@pytest.mark.requires_opnsense_source
def test_latest_spec_paths_resolve_to_real_controllers() -> None:
    """Every path in the latest committed spec resolves to a real controller.

    This test downloads the OPNsense source archive matching the latest
    committed spec via :class:`SourceDownloader`. If the download fails
    (e.g., no network in a developer sandbox), the test skips with a clear
    reason. CI pre-downloads the archive in a separate workflow step so the
    test runs unconditionally there.
    """
    available = list_available_specs()
    if not available:
        pytest.skip("No committed specs available")

    # list_available_specs() returns a list sorted by version key, so the
    # last entry is the highest version.
    latest_version = available[-1]
    spec_path = get_spec_path(latest_version)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    downloader = SourceDownloader()
    try:
        controllers_root = downloader.download(latest_version)
    except (RuntimeError, OSError) as exc:
        pytest.skip(
            f"Unable to materialize OPNsense source for {latest_version}: {exc}. "
            "Run `uv run python -c 'from opnsense_openapi.downloader import "
            f"SourceDownloader; SourceDownloader().download({latest_version!r})'` "
            "to populate the cache."
        )

    failures = check_spec_paths(spec, controllers_root)

    rendered = "\n".join(f"  {path}: {reason}" for path, reason in failures)
    assert not failures, (
        f"{len(failures)} path(s) in opnsense-{latest_version}.json do not "
        f"resolve to real OPNsense controllers under {controllers_root}:\n"
        f"{rendered}"
    )


def test_check_spec_paths_catches_collapsed_lowercase_controller(
    tmp_path: Path,
) -> None:
    """Lint catches the #32 regression class (collapsed-lowercase controller).

    This proves the lint would have rejected the broken spec emitted before
    PR #36: a path of ``/api/interfaces/vlansettings/...`` does not map to
    ``OPNsense/Interfaces/Api/VlanSettingsController.php`` under the
    snake_case-aware :func:`to_class_name` rule. ``vlansettings`` collapses
    to ``Vlansettings``, which is not the real controller filename.
    """
    controllers_root = _make_fake_controller_tree(
        tmp_path,
        {"Interfaces": ["VlanSettingsController.php"]},
    )

    broken_spec = {"paths": {"/api/interfaces/vlansettings/searchItem": {}}}
    failures = check_spec_paths(broken_spec, controllers_root)
    assert len(failures) == 1
    assert failures[0][0] == "/api/interfaces/vlansettings/searchItem"
    assert "VlansettingsController.php" in failures[0][1]

    # Conversely, the correctly snake_cased path resolves cleanly.
    correct_spec = {"paths": {"/api/interfaces/vlan_settings/searchItem": {}}}
    assert check_spec_paths(correct_spec, controllers_root) == []


def test_check_spec_paths_module_resolution_is_case_insensitive(
    tmp_path: Path,
) -> None:
    """Lint mirrors Mvc/Router.php's case-insensitive module fallback.

    URLs use lowercase module segments (``/api/dhcrelay``, ``/api/openvpn``)
    but the on-disk module directories are mixed-case (``DHCRelay``,
    ``OpenVPN``). The lint must not flag these as missing controllers.
    """
    controllers_root = _make_fake_controller_tree(
        tmp_path,
        {
            "DHCRelay": ["SettingsController.php"],
            "OpenVPN": ["InstancesController.php"],
        },
    )

    spec = {
        "paths": {
            "/api/dhcrelay/settings/get": {},
            "/api/openvpn/instances/search": {},
        }
    }
    assert check_spec_paths(spec, controllers_root) == []


def test_check_spec_paths_reports_missing_module(tmp_path: Path) -> None:
    """Lint reports a clear failure when the module directory is absent."""
    controllers_root = _make_fake_controller_tree(
        tmp_path,
        {"Interfaces": ["SettingsController.php"]},
    )

    spec = {"paths": {"/api/nonexistent/foo/bar": {}}}
    failures = check_spec_paths(spec, controllers_root)
    assert len(failures) == 1
    assert "module directory not found" in failures[0][1]


def test_check_spec_paths_skips_non_api_paths(tmp_path: Path) -> None:
    """Paths that don't match the 4+-segment ``/api/...`` shape are skipped.

    The lint is defensive: a well-formed spec shouldn't contain these, but
    we don't want to crash if one slips in.
    """
    controllers_root = _make_fake_controller_tree(tmp_path, {})

    spec = {
        "paths": {
            "/health": {},
            "/api/onlytwo": {},
            "/api/three/segments": {},
        }
    }
    assert check_spec_paths(spec, controllers_root) == []


def test_check_spec_paths_collects_all_failures(tmp_path: Path) -> None:
    """Lint collects every failing path, not just the first one."""
    controllers_root = _make_fake_controller_tree(
        tmp_path,
        {"Interfaces": ["SettingsController.php"]},
    )

    spec = {
        "paths": {
            "/api/interfaces/settings/get": {},  # ok
            "/api/interfaces/missing/get": {},  # bad controller
            "/api/nonexistent/foo/bar": {},  # bad module
        }
    }
    failures = check_spec_paths(spec, controllers_root)
    failed_paths = {path for path, _ in failures}
    assert failed_paths == {
        "/api/interfaces/missing/get",
        "/api/nonexistent/foo/bar",
    }
