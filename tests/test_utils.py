"""Tests for :mod:`opnsense_openapi.utils`."""

from __future__ import annotations

import pytest

from opnsense_openapi.utils import to_class_name, to_snake_case, validate_version


@pytest.mark.parametrize(
    "version",
    [
        "24.7",
        "24.7.1",
        "v24.7",
        "v24.7.1",
        "25.1.10",
        "1.0",
    ],
)
def test_validate_version_accepts_well_formed_versions(version: str) -> None:
    """validate_version returns True for well-formed version strings."""
    assert validate_version(version)


@pytest.mark.parametrize(
    "version",
    [
        "",
        "invalid",
        "24",
        "24.7.1.2",
        "abc.def",
        "24.7-rc1",
        "v",
        "24.",
    ],
)
def test_validate_version_rejects_malformed_versions(version: str) -> None:
    """validate_version returns False for malformed version strings."""
    assert not validate_version(version)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("findAlias", "find_alias"),
        ("AliasUtil", "alias_util"),
        ("get", "get"),
        ("setItem", "set_item"),
        ("", ""),
        ("lowercase", "lowercase"),
        ("HTTPServer", "h_t_t_p_server"),
    ],
)
def test_to_snake_case_conversions(source: str, expected: str) -> None:
    """to_snake_case converts camel/Pascal case into lowercase underscore form."""
    assert to_snake_case(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("firewall_alias", "FirewallAlias"),
        ("test", "Test"),
        ("api_controller_base", "ApiControllerBase"),
        ("", ""),
        ("single", "Single"),
        ("multi_part_name", "MultiPartName"),
    ],
)
def test_to_class_name_conversions(source: str, expected: str) -> None:
    """to_class_name joins snake_case tokens into a PascalCase identifier."""
    assert to_class_name(source) == expected
