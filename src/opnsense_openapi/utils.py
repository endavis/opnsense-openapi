"""Shared utility functions for opnsense_openapi."""

import re

VERSION_PATTERN = re.compile(r"^v?\d+\.\d+(\.\d+)?$")


def validate_version(version: str) -> bool:
    """Validate OPNsense version string format.

    Args:
        version: Version string to validate (e.g., "24.7", "24.7.1", "v24.7")

    Returns:
        True if valid, False otherwise
    """
    return bool(VERSION_PATTERN.match(version))


def to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case.

    Args:
        name: Name to convert

    Returns:
        snake_case name
    """
    result = ""
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result += "_"
        result += char.lower()
    return result


def to_class_name(name: str) -> str:
    """Convert snake_case to PascalCase class name.

    Args:
        name: snake_case name to convert

    Returns:
        PascalCase class name
    """
    return "".join(word.capitalize() for word in name.split("_"))
