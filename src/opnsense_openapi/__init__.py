"""OPNsense API Python wrapper generator and client."""

from opnsense_openapi.client import APIResponseError, OPNsenseClient, UnknownEndpointError
from opnsense_openapi.endpoints import SpecDiff, diff_specs, endpoint_exists, list_spec_endpoints
from opnsense_openapi.specs import (
    find_best_matching_spec,
    get_spec_path,
    get_specs_dir,
    is_version_covered,
    list_available_specs,
    newest_spec_version,
)

try:
    from opnsense_openapi._version import __version__
except ImportError:
    __version__ = "0.0.0+unknown"

# Backwards compatibility
SPECS_DIR = get_specs_dir()

__all__ = [
    "SPECS_DIR",
    "APIResponseError",
    "OPNsenseClient",
    "SpecDiff",
    "UnknownEndpointError",
    "diff_specs",
    "endpoint_exists",
    "find_best_matching_spec",
    "get_spec_path",
    "get_specs_dir",
    "is_version_covered",
    "list_available_specs",
    "list_spec_endpoints",
    "newest_spec_version",
]
