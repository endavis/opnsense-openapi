"""OPNsense API Python wrapper generator and client."""

from pathlib import Path

__version__ = "0.1.0"

SPECS_DIR = Path(__file__).parent / "specs"


def get_spec_path(version: str) -> Path:
    """Get path to bundled OpenAPI spec for a version.

    Args:
        version: OPNsense version (e.g., "25.7.6")

    Returns:
        Path to the spec file

    Raises:
        FileNotFoundError: If spec for version not found
    """
    spec_path = SPECS_DIR / f"opnsense-{version}.json"
    if not spec_path.exists():
        available = list_available_specs()
        raise FileNotFoundError(f"No spec for version {version}. Available: {available}")
    return spec_path


def list_available_specs() -> list[str]:
    """List available bundled spec versions.

    Returns:
        List of version strings
    """
    if not SPECS_DIR.exists():
        return []
    return [p.stem.replace("opnsense-", "") for p in SPECS_DIR.glob("opnsense-*.json")]
