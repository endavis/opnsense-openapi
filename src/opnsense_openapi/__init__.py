"""OPNsense API Python wrapper generator and client."""

from opnsense_openapi.client import OPNsenseClient
from opnsense_openapi.specs import (
    find_best_matching_spec,
    get_spec_path,
    get_specs_dir,
    list_available_specs,
)

try:
    from opnsense_openapi._version import __version__
except ImportError:
    __version__ = "0.0.0+unknown"

# Backwards compatibility
SPECS_DIR = get_specs_dir()

__all__ = [
    "SPECS_DIR",
    "OPNsenseClient",
    "find_best_matching_spec",
    "get_spec_path",
    "get_specs_dir",
    "list_available_specs",
]
