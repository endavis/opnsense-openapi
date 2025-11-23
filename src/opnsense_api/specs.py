"""Utilities for managing OPNsense API specification files."""

import re
from pathlib import Path


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
        match = re.match(r"opnsense-(.+)\.json$", spec_file.name)
        if match:
            versions.append(match.group(1))

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


def find_best_matching_spec(version: str) -> Path:
    """Find the best matching spec for a given version.

    If exact match exists, returns it. Otherwise, finds the closest version
    by matching major.minor and taking the highest patch version.

    Args:
        version: OPNsense version string (e.g., '24.7.1')

    Returns:
        Path to the best matching spec file

    Raises:
        FileNotFoundError: If no suitable spec can be found
    """
    # Try exact match first
    try:
        return get_spec_path(version)
    except FileNotFoundError:
        pass

    # Parse version components
    version_parts = version.split(".")
    if len(version_parts) < 2:
        raise FileNotFoundError(f"Invalid version format: {version}")

    major_minor = f"{version_parts[0]}.{version_parts[1]}"

    # Find all specs matching major.minor
    available = list_available_specs()
    matching = [v for v in available if v.startswith(f"{major_minor}.") or v == major_minor]

    if not matching:
        raise FileNotFoundError(
            f"No spec found for version {version} or {major_minor}.x. "
            f"Available versions: {', '.join(available)}"
        )

    # Return the highest matching version
    best_match = sorted(matching, key=_version_key)[-1]
    return get_spec_path(best_match)


def _version_key(version: str) -> tuple[int, ...]:
    """Convert version string to sortable tuple.

    Args:
        version: Version string like '24.7.1'

    Returns:
        Tuple of integers for sorting (24, 7, 1)
    """
    parts = version.split(".")
    return tuple(int(p) for p in parts)
