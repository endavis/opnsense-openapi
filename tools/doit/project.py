"""Project-specific doit tasks for opnsense-openapi.

Tasks here are NOT part of pyproject-template and will not be overwritten
during template syncs. Add project-specific workflows in this file.
"""

from typing import Any

from doit.tools import title_with_actions


def task_generate() -> dict[str, Any]:
    """Generate Python wrapper for a specific OPNsense version."""
    return {
        "actions": ["uv run opnsense-openapi generate %(version)s"],
        "params": [
            {
                "name": "version",
                "short": "v",
                "long": "version",
                "default": "24.7",
                "help": "OPNsense version to generate the wrapper for (e.g. 24.7, 25.1).",
            }
        ],
        "title": title_with_actions,
        "verbosity": 2,
    }
