"""OPNsense API Python wrapper generator and client."""

from opnsense_api.specs import (
    find_best_matching_spec,
    get_spec_path,
    get_specs_dir,
    list_available_specs,
)

__version__ = "0.1.0"

# Backwards compatibility
SPECS_DIR = get_specs_dir()

__all__ = [
    "find_best_matching_spec",
    "get_spec_path",
    "get_specs_dir",
    "list_available_specs",
    "SPECS_DIR",
]
