"""Shared utility functions for opnsense_api."""


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
