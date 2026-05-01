"""Utilities for managing OPNsense API specification files.

This module owns spec discovery and version-to-spec resolution. The matching
strategy is documented in
[`docs/development/spec-version-resolution.md`](../../docs/development/spec-version-resolution.md)
and codified in ADR-0001.

Two rules drive the resolver:

1. **`_N` security-patch suffixes are equivalent to the underlying release.**
   The OpenAPI surface does not change between security patches, so
   ``26.1.6_2`` resolves to the same spec as ``26.1.6``.
2. **"Floor" matching is the default.** When no exact spec is committed,
   ``find_best_matching_spec`` returns the highest spec **at or below** the
   requested version. The previous "highest" behavior is still available via
   ``mode="highest"`` for callers that explicitly want it.
"""

import re
from pathlib import Path
from typing import Literal

_SPEC_FILENAME_RE = re.compile(r"^opnsense-(?P<version>.+)\.json$")


def get_specs_dir() -> Path:
    """Get the directory containing OpenAPI spec files.

    Returns:
        Path to the specs directory
    """
    return Path(__file__).parent / "specs"


def list_available_specs() -> list[str]:
    """List all available OPNsense versions with specs.

    Returns:
        Sorted list of version strings (e.g., ['24.1', '24.7.1', '25.1'])
    """
    specs_dir = get_specs_dir()
    versions = []

    for spec_file in specs_dir.glob("opnsense-*.json"):
        # Extract version from filename: opnsense-24.7.1.json -> 24.7.1
        match = _SPEC_FILENAME_RE.match(spec_file.name)
        if match:
            versions.append(match.group("version"))

    return sorted(versions, key=_version_key)


def get_spec_path(version: str) -> Path:
    """Get the path to the OpenAPI spec file for a given version.

    Args:
        version: OPNsense version string (e.g., '24.7.1' or '24.7')

    Returns:
        Path to the spec file

    Raises:
        FileNotFoundError: If spec file for the version doesn't exist
    """
    specs_dir = get_specs_dir()
    spec_file = specs_dir / f"opnsense-{version}.json"

    if not spec_file.exists():
        raise FileNotFoundError(
            f"No spec file found for version {version}. "
            f"Available versions: {', '.join(list_available_specs())}"
        )

    return spec_file


def find_best_matching_spec(version: str, mode: Literal["highest", "floor"] = "floor") -> Path:
    """Find the best matching spec for a given version.

    If an exact match exists, returns it. Otherwise the resolver collects all
    specs sharing the requested ``major.minor`` and picks one based on
    ``mode``:

    - ``"floor"`` (default): the highest committed spec **at or below** the
      requested version. This is correct when the OPNsense box is between two
      committed specs — picking a higher spec would expose endpoints that may
      not exist on the box.
    - ``"highest"``: the highest committed spec sharing ``major.minor``. This
      is the legacy behavior, retained for callers that want to bias toward
      newer surfaces (e.g. interactive docs browsing).

    Security-patch suffixes (``26.1.6_2``) are normalized to their underlying
    release (``26.1.6``) for comparison, since the OpenAPI surface does not
    change between security patches of the same release.

    Args:
        version: OPNsense version string (e.g., '24.7.1' or '26.1.6_2')
        mode: Selection strategy. Default ``"floor"``.

    Returns:
        Path to the best matching spec file.

    Raises:
        FileNotFoundError: If no suitable spec can be found. In ``"floor"``
            mode this includes the case where no committed spec is at or
            below the requested version.
    """
    # Try exact match first (cheap short-circuit, independent of mode).
    try:
        return get_spec_path(version)
    except FileNotFoundError:
        pass

    # Parse version components.
    version_parts = version.split(".")
    if len(version_parts) < 2:
        raise FileNotFoundError(f"Invalid version format: {version}")

    major_minor = f"{version_parts[0]}.{version_parts[1]}"

    # Find all specs matching major.minor.
    available = list_available_specs()
    matching = [v for v in available if v.startswith(f"{major_minor}.") or v == major_minor]

    if not matching:
        raise FileNotFoundError(
            f"No spec found for version {version} or {major_minor}.x. "
            f"Available versions: {', '.join(available)}"
        )

    requested_key = _version_key(version)

    if mode == "floor":
        # Filter to specs at or below the requested version, then take highest.
        candidates = [v for v in matching if _version_key(v) <= requested_key]
        if not candidates:
            raise FileNotFoundError(
                f"No spec at or below version {version} (mode='floor'). "
                f"Available {major_minor}.x versions: {', '.join(matching)}"
            )
        best_match = sorted(candidates, key=_version_key)[-1]
    else:
        # mode == "highest": legacy behavior — take highest among major.minor.
        best_match = sorted(matching, key=_version_key)[-1]

    return get_spec_path(best_match)


def version_from_spec_path(path: Path) -> str:
    """Extract the version string from an ``opnsense-{version}.json`` path.

    This is the inverse of :func:`get_spec_path`. The client auto-generator
    uses it to derive a stable module directory from the *resolved* spec
    rather than the raw user-provided version, so that distinct
    security-patch revisions of the same release share a single generated
    client.

    Args:
        path: Path whose filename matches ``opnsense-{version}.json``.

    Returns:
        The version segment (e.g., ``"26.1.6"``).

    Raises:
        ValueError: If the filename does not match the expected shape.
    """
    match = _SPEC_FILENAME_RE.match(path.name)
    if not match:
        raise ValueError(f"Path {path} does not match expected 'opnsense-{{version}}.json' shape")
    return match.group("version")


def _version_key(version: str) -> tuple[int, ...]:
    """Convert version string to sortable tuple.

    Trailing ``_N`` security-patch suffixes on the **last** component are
    stripped before parsing, so ``26.1.6`` and ``26.1.6_2`` produce the same
    key. Security patches are equivalent to the underlying release for spec
    selection because the OpenAPI surface does not change between them.

    Args:
        version: Version string like ``"24.7.1"`` or ``"26.1.6_2"``.

    Returns:
        Tuple of integers for sorting (e.g., ``(24, 7, 1)`` or ``(26, 1, 6)``).
    """
    parts = version.split(".")
    if not parts:
        return ()
    # Strip a trailing _N suffix from the last component only. The OPNsense
    # surface does not differ between security patches.
    last = parts[-1]
    underscore_idx = last.find("_")
    if underscore_idx != -1:
        parts[-1] = last[:underscore_idx]
    return tuple(int(p) for p in parts)
