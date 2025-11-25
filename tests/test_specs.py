"""Tests for spec loading functions."""

import pytest

from opnsense_openapi import find_best_matching_spec, get_spec_path, list_available_specs


def test_list_available_specs() -> None:
    """Test listing available specs."""
    specs = list_available_specs()
    assert isinstance(specs, list)
    assert len(specs) > 0
    assert "25.7" in specs or "24.7" in specs  # At least one version present


def test_get_spec_path_valid() -> None:
    """Test getting path to a valid spec."""
    specs = list_available_specs()
    if specs:
        path = get_spec_path(specs[0])
        assert path.exists()
        assert path.suffix == ".json"


def test_get_spec_path_invalid() -> None:
    """Test error when spec not found."""
    with pytest.raises(FileNotFoundError) as exc_info:
        get_spec_path("99.99.99")
    assert "No spec" in str(exc_info.value)
    assert "Available" in str(exc_info.value)


def test_find_best_matching_spec_exact() -> None:
    """Test finding best match with exact version."""
    specs = list_available_specs()
    if "24.7.1" in specs:
        path = find_best_matching_spec("24.7.1")
        assert path.name == "opnsense-24.7.1.json"
        assert path.exists()


def test_find_best_matching_spec_fallback() -> None:
    """Test finding best match with non-existent patch version."""
    # Should find the highest 24.7.x
    path = find_best_matching_spec("24.7.999")
    assert path.name.startswith("opnsense-24.7.")
    assert path.exists()


def test_find_best_matching_spec_no_match() -> None:
    """Test finding best match with no suitable version."""
    with pytest.raises(FileNotFoundError) as exc_info:
        find_best_matching_spec("99.99.99")
    assert "No spec found" in str(exc_info.value)
